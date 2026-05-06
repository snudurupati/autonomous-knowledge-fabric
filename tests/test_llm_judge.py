import os
import time
import logging
from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.routing import OmnigraphRoutingManager
from engine.omnigraph.ingestion_sink import OmnigraphSink

# Enable logging to see the Fast-Path and Branching decisions
logging.basicConfig(level=logging.INFO)

def run_test():
    # Ensure the Google API key is set for Gemini
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Please set your GEMINI_API_KEY environment variable.")
        return

    sink = OmnigraphSink(use_buffering=True)
    router = OmnigraphRoutingManager(sink=sink)

    print("\n--- Phase 1: Ingest 'Main' Candidate (Strong Signal) ---")
    # This event has a CIK number, so it triggers the FAST-PATH and goes straight to 'main'
    main_event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Apple Inc.",
        cik_number="0000320193", # Strong signal
        risk_signals=[RiskSignal.EXECUTIVE_DEPARTURE],
        raw_text="Apple Inc. (CIK: 0000320193) announced the departure of a key executive today."
    )
    router.process_event(main_event)
    
    # Wait a moment for the commit to settle
    time.sleep(1)

    print("\n--- Phase 2: Ingest 'Fragment' (Weak Signal) ---")
    # This event only has a name, so it gets buffered into a side-branch
    fragment_event = AccountEvent(
        source=EventSource.ZENDESK,
        company_name="Apple", # Weak signal, missing identifiers
        risk_signals=[RiskSignal.CRITICAL_SUPPORT],
        raw_text="Customer reported a critical kernel panic on the latest macOS beta."
    )
    
    # process_event returns False when branched. We need the branch ID from the sink.
    # To capture the branch ID cleanly for the test, we'll bypass the router for the fragment insertion
    branch_id = sink.ingest_unverified_entity(fragment_event)
    print(f"Created Fragment Branch: {branch_id}")
    
    time.sleep(1)

    print("\n--- Phase 3: Execute Tier-3 LLM Judge ---")
    print(f"Asking Gemini 2.5 Flash to compare branch '{branch_id}' against 'main'...")
    
    # The node_key for the fragment will be its normalized name
    node_key = fragment_event.company_name
    
    # Run the judge
    success = router.evaluate_and_resolve(
        branch_id=branch_id, 
        node_key=node_key, 
        company_name="Apple" # The search query for candidates
    )

    print(f"\nResult: {'✅ MERGED' if success else '❌ REJECTED'}")

if __name__ == "__main__":
    run_test()

