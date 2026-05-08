# pipelines/routing.py
# Shared logic for event buffering and promotion using Omnigraph side-branches.

import os
import logging
from typing import Optional, Any
from models.account_event import AccountEvent
from engine.omnigraph.ingestion_sink import OmnigraphSink
from google import genai
import instructor
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ResolutionDecision(BaseModel):
    is_match: bool

class BatchResolutionItem(BaseModel):
    branch_id: str
    is_match: bool
    reasoning: str

class BatchResolutionResponse(BaseModel):
    decisions: list[BatchResolutionItem]

class OmnigraphRoutingManager:
    """
    Manages entity resolution routing using Omnigraph side-branches.
    Replaces the legacy in-memory GhostNodeManager.
    """
    def __init__(self, sink: Optional[OmnigraphSink] = None):
        self.sink = sink or OmnigraphSink()

    def process_event(self, event: AccountEvent) -> bool:
        """
        Process an event. 
        If it's a "Strong Signal" (has identifiers), promotes immediately via FAST-PATH.
        Otherwise, creates a side-branch in Omnigraph for future resolution.
        
        Returns True if promoted (merged or direct to main), False if branched.
        """
        # 1. Strong Signal Check (Immediate Promotion / Fast-Path)
        # If we have identifiers, we bypass side-branches to avoid merge conflicts
        # and non-graceful server errors.
        has_strong_signal = bool(event.cik_number or event.company_domain or event.account_id)
        
        if has_strong_signal:
            logger.info(f"Fast-Path: Ingesting high-confidence event for {event.company_name} directly to main via buffer")
            try:
                self.sink.ingest_event(event)
                return True
            except Exception as e:
                logger.error(f"Fast-Path ingestion failed for {event.company_name}: {e}")
                return False

        # 2. Branch-Based Buffering: Weak signals start in their own branch
        # This replaces the in-memory self.buffer from GhostNodeManager
        branch_id = self.sink.ingest_unverified_entity(event)
        
        if not branch_id:
            logger.error(f"Routing failed: Could not create branch for {event.company_name}")
            return False

        # For "Weak Signals" (name only), we keep the branch open.
        # In Sprint 17+, a separate corroboration service or Tier-3 LLM 
        # will call evaluate_and_merge later.
        logger.info(f"Event branched: {event.company_name} is now buffered in Omnigraph branch '{branch_id}'")
        return False

    def evaluate_and_resolve(self, branch_id: str, node_key: str, company_name: str) -> bool:
        """
        Executes Tier-3 LLM Judge to evaluate a side-branch fragment against main candidates.
        """
        # 1. Fetch Fragment
        try:
            fragment_context = self.sink.client.get_account_context(node_key, branch=branch_id)
        except Exception as e:
            logger.error(f"Failed to fetch fragment context for {node_key} on branch {branch_id}: {e}")
            return False

        # 2. Search Candidates
        try:
            candidates = self.sink.client._execute(
                "read", 
                "complex_search.gq", 
                {"query": company_name}, 
                branch="main"
            )
        except Exception as e:
            logger.error(f"Failed to search candidates for {company_name}: {e}")
            return False

        # 3. Evaluate
        try:
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            genai_client = genai.Client(api_key=api_key)
            client = instructor.from_genai(
                genai_client,
                mode=instructor.Mode.GENAI_STRUCTURED_OUTPUTS,
            )
            
            resp = client.chat.completions.create(
                model="gemini-2.5-flash",
                response_model=ResolutionDecision,
                messages=[
                    {"role": "system", "content": "You are an entity resolution judge. Determine if the fragment belongs to one of the main branch candidates."},
                    {"role": "user", "content": f"Fragment Context: {fragment_context}\n\nCandidates Context: {candidates}\n\nDoes the fragment match a candidate?"}
                ]
            )
            
            is_match = resp.is_match
        except Exception as e:
            logger.error(f"LLM evaluation failed for {company_name}: {e}")
            raise e  # Raise the exception so the caller can trigger rate-limit backoffs

        # 4. Execute
        if is_match:
            logger.info(f"Tier-3 LLM matched fragment {node_key} to a candidate. Merging branch {branch_id}.")
            return self.sink.evaluate_and_merge(branch_id, evidence_score=100)
            
        logger.info(f"Tier-3 LLM rejected fragment {node_key}. Branch {branch_id} remains open.")
        return False

    def evaluate_and_resolve_batch(self, fragments: list[dict]) -> dict:
        """
        Executes Tier-3 LLM Judge on a batch of side-branch fragments.
        :param fragments: List of dicts with {'branch_id', 'node_key', 'company_name'}
        :return: Dict with success/failure stats
        """
        if not fragments:
            return {"success": 0, "failure": 0, "skipped": 0}

        # 1. Gather Context for all fragments
        batch_context = []
        for frag in fragments:
            try:
                branch_id = frag["branch_id"]
                node_key = frag["node_key"]
                name = frag["company_name"]
                
                context = self.sink.client.get_account_context(node_key, branch=branch_id)
                candidates = self.sink.client._execute(
                    "read", 
                    "complex_search.gq", 
                    {"query": name}, 
                    branch="main"
                )
                
                batch_context.append({
                    "branch_id": branch_id,
                    "fragment_context": context,
                    "candidates": candidates
                })
            except Exception as e:
                logger.error(f"Failed to gather context for fragment {frag.get('branch_id')}: {e}")

        if not batch_context:
            return {"success": 0, "failure": 0, "skipped": len(fragments)}

        # 2. Evaluate Batch via LLM
        try:
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            genai_client = genai.Client(api_key=api_key)
            client = instructor.from_genai(
                genai_client,
                mode=instructor.Mode.GENAI_STRUCTURED_OUTPUTS,
            )
            
            prompt = """You are an expert entity resolution judge. 
Evaluate the following batch of account fragments against their potential candidates on the main branch.
For each fragment, determine if it is a definite match to one of its provided candidates.

Criteria:
1. Highly similar company names (accounting for common abbreviations and minor typos).
2. Shared identifiers like CIK or Domain.
3. Overlapping risk signals or context that strongly implies they are the same legal entity.

If a fragment matches a candidate, set is_match=True. Otherwise, set is_match=False.
Always provide a brief reasoning for your decision.

"""
            for i, item in enumerate(batch_context):
                prompt += f"--- Fragment {i+1} (Branch: {item['branch_id']}) ---\n"
                prompt += f"Fragment Info: {item['fragment_context']}\n"
                prompt += f"Main Branch Candidates: {item['candidates']}\n\n"
            
            prompt += "Return a decision for EVERY fragment in the batch."

            resp = client.chat.completions.create(
                model="gemini-2.5-flash",
                # response_model is required for Mode.GENAI_STRUCTURED_OUTPUTS
                response_model=BatchResolutionResponse,
                messages=[
                    {"role": "system", "content": "You are a precise entity resolution engine."},
                    {"role": "user", "content": prompt}
                ]
            )
        except Exception as e:
            logger.error(f"Batch LLM evaluation failed: {e}")
            raise e

        # 3. Process Decisions
        stats = {"success": 0, "failure": 0, "skipped": 0}
        decision_map = {d.branch_id: d for d in resp.decisions}
        
        for frag in batch_context:
            branch_id = frag["branch_id"]
            decision = decision_map.get(branch_id)
            
            if not decision:
                stats["skipped"] += 1
                continue
                
            if decision.is_match:
                logger.info(f"Batch Resolver: Matched {branch_id}. Reasoning: {decision.reasoning}")
                if self.sink.evaluate_and_merge(branch_id, evidence_score=100):
                    stats["success"] += 1
                else:
                    stats["failure"] += 1
            else:
                logger.info(f"Batch Resolver: Rejected {branch_id}. Reasoning: {decision.reasoning}")
                stats["failure"] += 1
                
        return stats

_manager: Optional[OmnigraphRoutingManager] = None

def get_routing_manager() -> OmnigraphRoutingManager:
    """Singleton getter for the routing manager."""
    global _manager
    if _manager is None:
        # Enable batching to optimize S3 commits
        sink = OmnigraphSink(use_buffering=True, batch_size=25, flush_interval_secs=300.0)
        _manager = OmnigraphRoutingManager(sink=sink)
    return _manager
