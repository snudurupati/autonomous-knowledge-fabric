# pipelines/batch_resolver.py
# Periodic resolver that scans Omnigraph side-branches and uses Tier-3 LLM Judge
# to merge them into the main knowledge fabric.

import time
import requests
import logging
import os
from pipelines.routing import get_routing_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BatchResolver:
    def __init__(self, server_url: str = "http://127.0.0.1:8080"):
        self.server_url = server_url
        self.router = get_routing_manager()

    def get_all_branches(self):
        """Fetch all branch names from Omnigraph."""
        try:
            resp = requests.get(f"{self.server_url}/branches")
            resp.raise_for_status()
            return resp.json().get("branches", [])
        except Exception as e:
            logger.error(f"Failed to fetch branches: {e}")
            return []

    def resolve_all(self):
        """Iterate through fragment branches and attempt resolution."""
        branches = self.get_all_branches()
        # Filter for fragment branches (exclude 'main')
        fragments = [b for b in branches if b.startswith("fragment-") or b.startswith("weak-")]
        
        if not fragments:
            logger.info("No fragment branches found for resolution.")
            return

        logger.info(f"🔍 Found {len(fragments)} branches awaiting resolution.")
        
        resolved_count = 0
        for branch_id in fragments:
            logger.info(f"--- Resolving branch: {branch_id} ---")
            
            # 1. Identify the 'primary' company name in this branch
            # We use a simple heuristic: the branch name or a quick read
            # In our sink, we use node_key = company_name. 
            # For fragment branches, we'll try to extract the name from the branch context.
            try:
                # Fetch any account node from this branch using a simple query
                # to avoid BM25 index issues on newly created side-branches.
                resp = self.router.sink.client._execute(
                    "read", 
                    "get_high_risk_accounts.gq", 
                    {"min_score": 0}, 
                    branch=branch_id
                )
                rows = resp.get("rows", [])
                if not rows:
                    logger.warning(f"Branch {branch_id} is empty. Deleting.")
                    requests.delete(f"{self.server_url}/branches/{branch_id}")
                    continue

                # Get the first account found in the branch
                company_name = rows[0].get("a.name")
                node_key = rows[0].get("a.node_key")
                
                logger.info(f"Branch '{branch_id}' appears to be about '{company_name}'")
                
                # 2. Invoke the Tier-3 LLM Judge
                success = self.router.evaluate_and_resolve(
                    branch_id=branch_id,
                    node_key=node_key,
                    company_name=company_name
                )
                
                if success:
                    resolved_count += 1
                    logger.info(f"✅ Resolved and merged branch {branch_id}")
                else:
                    logger.info(f"⏳ Branch {branch_id} remains open (no match or rejected)")
                    
            except Exception as e:
                logger.error(f"Error resolving branch {branch_id}: {e}")

        logger.info(f"🏁 Batch resolution complete. Resolved {resolved_count}/{len(fragments)} branches.")

def run_loop(interval_hours: float = 1.0):
    """Continuous loop for periodic resolution."""
    resolver = BatchResolver()
    logger.info(f"🚀 Batch Resolver started. Running every {interval_hours} hours.")
    
    while True:
        resolver.resolve_all()
        logger.info(f"Sleeping for {interval_hours} hours...")
        time.sleep(interval_hours * 3600)

if __name__ == "__main__":
    import sys
    # Take optional interval from command line
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    
    # If interval is 0, run once and exit (for manual trigger)
    if interval == 0:
        BatchResolver().resolve_all()
    else:
        run_loop(interval)
