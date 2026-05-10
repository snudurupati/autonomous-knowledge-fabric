import requests
from engine.omnigraph.client import OmnigraphClient

def test_graph_deduplication():
    client = OmnigraphClient("http://127.0.0.1:8080")
    print("🚀 Starting Graph Deduplication Test...")

    # 1. Create the base account
    client.insert_account(
        name="Dedupe Corp",
        node_key="dedupe_corp",
        risk_score=0,
        branch="main"
    )
    print("✅ Created base account 'Dedupe Corp'.")

    # 2. Insert Event A (First time)
    # We simulate the deterministic ID the pipeline would generate
    client.insert_event(
        event_id="deterministic-hash-001",
        source="SEC_EDGAR",
        timestamp="2026-05-10T10:00:00Z",
        risk_signals=[],
        raw_text="This is the first filing.",
        branch="main"
    )
    client.link_account_event("dedupe_corp", "deterministic-hash-001", branch="main")
    print("✅ Inserted Event A (First time).")

    # 3. Insert Event A (Second time - The Duplicate!)
    # This simulates the 1-hour amnesia loop re-reading the exact same filing
    client.insert_event(
        event_id="deterministic-hash-001",
        source="SEC_EDGAR",
        timestamp="2026-05-10T11:00:00Z", # Even if timestamp changes slightly
        risk_signals=[],
        raw_text="This is the first filing.",
        branch="main"
    )
    client.link_account_event("dedupe_corp", "deterministic-hash-001", branch="main")
    print("✅ Inserted Event A (Second time - Duplicate).")

    # 4. Insert Event B (A genuinely new filing)
    client.insert_event(
        event_id="deterministic-hash-002",
        source="SEC_EDGAR",
        timestamp="2026-05-10T12:00:00Z",
        risk_signals=[],
        raw_text="This is a DIFFERENT filing.",
        branch="main"
    )
    client.link_account_event("dedupe_corp", "deterministic-hash-002", branch="main")
    print("✅ Inserted Event B (New filing).")

    # 5. Query the database to count the events linked to Dedupe Corp
    url = "http://127.0.0.1:8080/read"
    payload = {
        "query_source": """
            query count_test_events() {
                match {
                    $a: Account { node_key: "dedupe_corp" }
                    $a has_event $e
                    $e: AccountEvent
                }
                return { $e.event_id, $e.raw_text }
            }
        """,
        "target": {"branch": "main"}
    }
    
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    
    rows = data.get("rows", [])
    print(f"\n📊 Final Result: Omnigraph returned {len(rows)} events for Dedupe Corp.")
    
    for i, row in enumerate(rows):
        print(f"  Event {i+1}: ID={row['e.event_id']}, Text='{row['e.raw_text']}'")

    if len(rows) == 2:
        print("\n🎉 TEST PASSED: Omnigraph successfully deduplicated Event A!")
    else:
        print(f"\n❌ TEST FAILED: Expected 2 events, found {len(rows)}.")

if __name__ == "__main__":
    test_graph_deduplication()
