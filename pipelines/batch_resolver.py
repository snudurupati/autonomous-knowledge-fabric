import sys
import os
import time
import logging
import requests
from pydantic import BaseModel
from google import genai
import instructor
from engine.omnigraph.client import OmnigraphClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BatchResolutionItem(BaseModel):
    branch_id: str
    is_match: bool
    reasoning: str

class BatchResolutionResponse(BaseModel):
    decisions: list[BatchResolutionItem]

def get_fragment_metadata_safe(client, branch_id, max_retries=3):
    """
    Phase 1: Safe Discovery
    Sequentially and safely fetches fragment metadata and main-branch candidates.
    Handles 'False 404' and '500 Internal Server Error' storage anomalies via retries.
    """
    for attempt in range(max_retries):
        try:
            # 1. Fetch Fragment
            res = client._execute("read", "list_accounts.gq", {}, branch=branch_id, sync_branch=True)
            rows = res.get("rows", [])
            if not rows:
                return None
            
            acc = rows[0]
            node_key = acc.get("a.node_key") or acc.get("node_key")
            company_name = acc.get("a.name") or acc.get("name")
            
            if node_key and company_name:
                # 2. Gather Context for LLM
                context = client.get_account_context(node_key, branch=branch_id)
                candidates = client._execute("read", "complex_search.gq", {"query": company_name}, branch="main")
                
                return {
                    "branch_id": branch_id,
                    "node_key": node_key,
                    "company_name": company_name,
                    "fragment_context": context,
                    "candidates": candidates
                }
            return None
        except Exception as e:
            error_str = str(e).lower()
            if "404" in error_str or "500" in error_str or "internal" in error_str:
                logger.warning(f"Transient storage error reading {branch_id} (Attempt {attempt+1}/{max_retries}). Retrying in 2s...")
                time.sleep(2)
            else:
                logger.error(f"Failed to read branch {branch_id}: {e}")
                break
    
    logger.warning(f"Skipping {branch_id} after {max_retries} failed metadata collection attempts.")
    return None

def evaluate_batch_llm(batch_context):
    """
    Phase 2: Decoupled LLM Evaluation
    Calls the LLM Judge to evaluate all fragments in the batch. No DB operations here.
    """
    if not batch_context:
        return []
        
    try:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("API key missing")
            
        genai_client = genai.Client(api_key=api_key)
        client = instructor.from_genai(
            genai_client,
            mode=instructor.Mode.GENAI_STRUCTURED_OUTPUTS,
        )
        
        prompt = "You are an expert entity resolution judge.\n"
        prompt += "Evaluate the following batch of account fragments against their potential candidates on the main branch.\n"
        prompt += "For each fragment, determine if it is a definite match to one of its provided candidates.\n\n"
        prompt += "Criteria:\n1. Highly similar company names (accounting for common abbreviations and minor typos).\n2. Shared identifiers like CIK or Domain.\n3. Overlapping risk signals or context that strongly implies they are the same legal entity.\n\n"
        
        for i, item in enumerate(batch_context):
            prompt += f"--- Fragment {i+1} (Branch: {item['branch_id']}) ---\n"
            prompt += f"Fragment Info: {item['fragment_context']}\n"
            prompt += f"Main Branch Candidates: {item['candidates']}\n\n"
        
        prompt += "Return a decision for EVERY fragment in the batch. Set is_match=True for a match, False otherwise. Provide brief reasoning."

        resp = client.chat.completions.create(
            model="gemini-2.5-flash",
            response_model=BatchResolutionResponse,
            messages=[
                {"role": "system", "content": "You are a precise entity resolution engine."},
                {"role": "user", "content": prompt}
            ]
        )
        return resp.decisions
    except Exception as e:
        logger.error(f"Batch LLM evaluation failed: {e}")
        raise e

def execute_decisions_safe(server_url, decisions):
    """
    Phase 3: Conflict-Aware Execution
    Safely executes merges with an Anti-409 retry loop and mandatory settle delays.
    Guarantees cleanup by deleting branches regardless of acceptance/rejection.
    """
    stats = {"merged": 0, "rejected": 0, "failed": 0}
    
    for decision in decisions:
        branch_id = decision.branch_id
        
        # Scenario A: Rejected -> Immediate Purge
        if not decision.is_match:
            logger.info(f"[-] REJECTED {branch_id}. Reason: {decision.reasoning}. Purging branch...")
            try:
                requests.delete(f"{server_url}/branches/{branch_id}").raise_for_status()
                stats["rejected"] += 1
                time.sleep(0.5) # Slight pause to prevent immediate 404s on next call
            except Exception as e:
                logger.error(f"Failed to delete rejected branch {branch_id}: {e}")
            continue
        
        # Scenario B: Matched -> Merge with 409 Retry -> Purge
        logger.info(f"[+] MATCHED {branch_id}. Reason: {decision.reasoning}. Attempting merge...")
        merged = False
        
        for attempt in range(5):
            try:
                merge_resp = requests.post(f"{server_url}/branches/merge?sync_branch=true", json={
                    "source": branch_id,
                    "target": "main",
                    "strategy": "merge"
                })
                merge_resp.raise_for_status()
                merged = True
                break
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 409:
                    logger.warning(f"409 Conflict merging {branch_id} (Attempt {attempt+1}/5). Main branch moved. Retrying in 3s...")
                    time.sleep(3)
                else:
                    logger.error(f"HTTP Error merging {branch_id}: {e}")
                    break
            except Exception as e:
                logger.error(f"Unexpected error merging {branch_id}: {e}")
                break
        
        if merged:
            logger.info(f"✅ SUCCESS: Merged {branch_id}. Purging source branch...")
            try:
                requests.delete(f"{server_url}/branches/{branch_id}").raise_for_status()
                stats["merged"] += 1
            except Exception as e:
                logger.error(f"Failed to delete merged branch {branch_id}: {e}")
            
            # MANDATORY SETTLE DELAY
            # Gives local RustFS emulator time to update main manifest before next loop
            time.sleep(1.5)
        else:
            logger.error(f"❌ FAILED: Exhausted retries or hard error merging {branch_id}.")
            stats["failed"] += 1

    return stats

def run_batch_resolver():
    """Main Orchestrator for the Resilient Sweeper pattern."""
    server_url = os.getenv("OMNIGRAPH_SERVER_URL", "http://127.0.0.1:8080")
    client = OmnigraphClient(server_url)
    
    logger.info("📡 Fetching branches from server...")
    try:
        resp = requests.get(f"{server_url}/branches")
        resp.raise_for_status()
        branches = resp.json().get("branches", [])
    except Exception as e:
        logger.error(f"Failed to fetch branches: {e}")
        return

    fragments = [b for b in branches if b.startswith("fragment-") or b.startswith("weak-")]
    logger.info(f"Found {len(fragments)} side-branches to evaluate.")
    if not fragments:
        return

    logger.info("--- Phase 1: Safe Discovery ---")
    batch_context = []
    for b in fragments:
        meta = get_fragment_metadata_safe(client, b)
        if meta:
            batch_context.append(meta)
        time.sleep(0.5) # Sequential pacing

    logger.info(f"Successfully collected metadata for {len(batch_context)} valid fragments.")

    batch_size = 20
    for i in range(0, len(batch_context), batch_size):
        chunk = batch_context[i:i + batch_size]
        logger.info(f"\n--- Processing Batch {i//batch_size + 1} ({len(chunk)} fragments) ---")
        
        try:
            logger.info("--- Phase 2: Decoupled LLM Evaluation ---")
            decisions = evaluate_batch_llm(chunk)
            
            logger.info("--- Phase 3: Conflict-Aware Execution ---")
            stats = execute_decisions_safe(server_url, decisions)
            
            logger.info(f"📊 Batch {i//batch_size + 1} Result: Merged={stats['merged']}, Rejected={stats['rejected']}, Failed={stats['failed']}")
            
            # API Rate limit safety net
            logger.info("Sleeping 10s between batches...")
            time.sleep(10)
            
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "resource_exhausted" in error_msg:
                logger.error(f"🚨 RATE LIMIT EXHAUSTED (429). Backing off for 60 seconds...")
                time.sleep(60)
            else:
                logger.error(f"❌ Error during batch resolution: {e}")

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    run_batch_resolver()
