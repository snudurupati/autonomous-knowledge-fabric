import sys
import os
import time
import requests
from engine.omnigraph.client import OmnigraphClient
from pipelines.routing import get_routing_manager

def run_batch_resolver():
    server_url = os.getenv("OMNIGRAPH_SERVER_URL", "http://127.0.0.1:8080")
    client = OmnigraphClient(server_url)
    router = get_routing_manager()
    
    # 1. Get all branches
    try:
        resp = requests.get(f"{server_url}/branches")
        resp.raise_for_status()
        branches = resp.json().get("branches", [])
    except Exception as e:
        print(f"Failed to fetch branches: {e}")
        return

    fragments = [b for b in branches if b.startswith("fragment-") or b.startswith("weak-")]
    print(f"Found {len(fragments)} side-branches to evaluate.")

    for branch_id in fragments:
        print(f"\n--- Evaluating Branch: {branch_id} ---")
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                # Get the account name and node_key from this branch
                try:
                    res = client._execute("read", "list_accounts.gq", {}, branch=branch_id)
                except Exception as e:
                    print(f"⚠️ Skipping branch {branch_id} due to read error: {e}")
                    break
                    
                accounts = res.get("rows", [])
                
                if not accounts:
                    print(f"No accounts found in branch {branch_id}. Skipping.")
                    break
                
                resolved_all = True
                for acc in accounts:
                    node_key = acc.get("a.node_key") or acc.get("node_key")
                    company_name = acc.get("a.name") or acc.get("name")
                    
                    if not node_key or not company_name:
                        continue
                    
                    print(f"Evaluating entity: '{company_name}' (key: {node_key}) [Attempt {attempt + 1}]")
                    
                    try:
                        success = router.evaluate_and_resolve(
                            branch_id=branch_id,
                            node_key=node_key,
                            company_name=company_name
                        )
                        
                        if success:
                            print(f"✅ SUCCESSFULLY MERGED {branch_id} for '{company_name}'")
                        else:
                            print(f"ℹ️ RESOLVER: No confident match found for '{company_name}' on main.")
                        
                        print("Sleeping 6s to maintain ~10 RPM...")
                        time.sleep(6)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "429" in error_msg or "resource_exhausted" in error_msg or "too many requests" in error_msg:
                            print(f"🚨 RATE LIMIT EXHAUSTED (429) after internal retries: {e}")
                            print("Backing off for 60 seconds before retrying THIS branch...")
                            time.sleep(60)
                            resolved_all = False
                            break # Break inner loop to retry the whole branch
                        else:
                            print(f"❌ Error during resolution for {branch_id}: {e}")
                            continue
                
                if resolved_all:
                    break # Success or non-retryable skip, move to next branch
                else:
                    attempt += 1 # Retryable 429 hit, increment attempt counter
                    
            except Exception as e:
                print(f"Error processing branch {branch_id}: {e}")
                break

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    run_batch_resolver()
