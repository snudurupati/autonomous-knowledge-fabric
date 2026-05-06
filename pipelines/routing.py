# pipelines/routing.py
# Shared logic for event buffering and promotion using Omnigraph side-branches.

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
            client = instructor.from_genai(
                genai.Client(),
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
            return False

        # 4. Execute
        if is_match:
            logger.info(f"Tier-3 LLM matched fragment {node_key} to a candidate. Merging branch {branch_id}.")
            return self.sink.evaluate_and_merge(branch_id, evidence_score=100)
            
        logger.info(f"Tier-3 LLM rejected fragment {node_key}. Branch {branch_id} remains open.")
        return False

_manager: Optional[OmnigraphRoutingManager] = None

def get_routing_manager() -> OmnigraphRoutingManager:
    """Singleton getter for the routing manager."""
    global _manager
    if _manager is None:
        # Enable batching to optimize S3 commits
        sink = OmnigraphSink(use_buffering=True, batch_size=20, flush_interval_secs=3.0)
        _manager = OmnigraphRoutingManager(sink=sink)
    return _manager
global _manager
    if _manager is None:
        # Enable batching to optimize S3 commits
        sink = OmnigraphSink(use_buffering=True, batch_size=100, flush_interval_secs=3.0)
        _manager = OmnigraphRoutingManager(sink=sink)
    return _manager
