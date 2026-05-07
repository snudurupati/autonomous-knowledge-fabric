# verify_llm_judge.py
# Targeted test to verify the Tier-3 LLM Judge and branch merging logic.

import os
import time
from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.routing import get_routing_manager
from engine.omnigraph.ingestion_sink import OmnigraphSink

def test_llm_judge():
    # 1. Environment Check
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY is not set. The LLM Judge requires an API key.")
        return

    # Use a sink with immediate commits for the test to avoid batching delays
    sink = OmnigraphSink(use_buffering=False)
    router = get_routing_manager()
    router.sink = sink # Override for the test

    print("\n--- Phase 1: Establish 'Main' Account (Strong Signal) ---")
    # This event has a CIK, so it goes straight to 'main'
    main_event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Microsoft Corporation",
        cik_number="0000789019",
        risk_signals=[RiskSignal.EXECUTIVE_DEPARTURE],
        raw_text="Microsoft (CIK 789019) announced that a senior VP is departing."
    )
    router.process_event(main_event)
    print("✅ Created Microsoft on 'main'")
    time.sleep(2) # Wait for S3 commit

    print("\n--- Phase 2: Create 'Fragment' (Weak Signal) ---")
    # This event only has a name, so it will be branched
    fragment_event = AccountEvent(
        source=EventSource.ZENDESK,
        company_name="Microsoft", # Partial name, no CIK
        risk_signals=[RiskSignal.CRITICAL_SUPPORT],
        raw_text="Major outage reported on Azure East US region."
    )
    
    # We manually use the sink to get the branch ID
    branch_id = sink.ingest_unverified_entity(fragment_event)
    print(f"✅ Created side-branch for fragment: {branch_id}")
    time.sleep(2)

    print("\n--- Phase 3: Trigger Tier-3 LLM Judge ---")
    print(f"Evaluating if branch '{branch_id}' matches 'Microsoft Corporation' on main...")
    
    # The node_key for the fragment is the company name
    success = router.evaluate_and_resolve(
        branch_id=branch_id,
        node_key=fragment_event.company_name,
        company_name="Microsoft" # Search query for candidates
    )

    if success:
        print("\n🏆 SUCCESS: The LLM matched the fragment and MERGED the branch!")
        print("You should now see both events under 'Microsoft Corporation' in the dashboard.")
    else:
        print("\n❌ FAILED: The LLM did not match the fragment or the merge failed.")

if __name__ == "__main__":
    test_llm_judge()
