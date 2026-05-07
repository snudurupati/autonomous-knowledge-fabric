import sys
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from engine.omnigraph.client import OmnigraphClient
from pipelines.routing import get_routing_manager

def get_fragment_metadata(client, branch_id):
    """Worker function for parallel metadata collection."""
    try:
        res = client._execute("read", "list_accounts.gq", {}, branch=branch_id)
        rows = res.get("rows", [])
        if not rows:
            return None
        
        acc = rows[0]
        node_key = acc.get("a.node_key") or acc.get("node_key")
        company_name = acc.get("a.name") or acc.get("name")
        if node_key and company_name:
            return {
                "branch_id": branch_id,
                "node_key": node_key,
                "company_name": company_name
            }
    except Exception as e:
        print(f"⚠️ Error reading branch {branch_id}: {e}")
    return None

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

    # 2. Collect metadata in parallel (S3 Head reads are slow)
    print(f"Collecting metadata for {len(fragments)} fragments using parallel workers...")
    fragment_metadata = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_fragment_metadata, client, b) for b in fragments]
        for future in futures:
            result = future.result()
            if result:
                fragment_metadata.append(result)

    print(f"Collected metadata for {len(fragment_metadata)} valid fragments.")

    # 3. Process in batches of 20
    batch_size = 20
    for i in range(0, len(fragment_metadata), batch_size):
        chunk = fragment_metadata[i:i + batch_size]
        print(f"\n--- Processing Batch {i//batch_size + 1} ({len(chunk)} fragments) ---")
        
        try:
            results = router.evaluate_and_resolve_batch(chunk)
            print(f"Batch Result: Success={results['success']}, Failure={results['failure']}, Skipped={results['skipped']}")
            
            # To stay under the ~10 RPM limit for general safety, even though we use fewer calls now
            print("Sleeping 10s between batches...")
            time.sleep(10)
            
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "resource_exhausted" in error_msg:
                print(f"🚨 RATE LIMIT EXHAUSTED (429). Backing off for 60 seconds...")
                time.sleep(60)
            else:
                print(f"❌ Error during batch resolution: {e}")

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    run_batch_resolver()
