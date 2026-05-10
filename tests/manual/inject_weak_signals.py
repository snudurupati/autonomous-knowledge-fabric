# tests/manual/inject_weak_signals.py
import os
import sys
import uuid
from datetime import datetime, timezone
from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.routing import get_routing_manager

def inject_weak_signals(count=10):
    manager = get_routing_manager()
    
    # We use names that are slightly ambiguous or related to SEED_COMPANIES
    # but missing identifiers (CIK, Domain, ID)
    test_data = [
        {"name": "Apple Inc.", "reason": "Ambiguous Apple"},
        {"name": "MSFT Corp", "reason": "Ambiguous Microsoft"},
        {"name": "Tesla Motors", "reason": "Ambiguous Tesla"},
        {"name": "J.P. Morgan", "reason": "Ambiguous JPMorgan"},
        {"name": "Walmart Stores", "reason": "Ambiguous Walmart"},
    ]

    print(f"🚀 Injecting {count} weak signal events into crm-test...")
    
    for i in range(count):
        data = test_data[i % len(test_data)]
        event = AccountEvent(
            event_id=str(uuid.uuid4()),
            source=EventSource.SEC_EDGAR,
            company_name=data["name"],
            company_domain=None, # WEAK SIGNAL: No Domain
            cik_number=None,     # WEAK SIGNAL: No CIK
            account_id=None,     # WEAK SIGNAL: No ID
            risk_signals=[RiskSignal.CRITICAL_SUPPORT],
            raw_text=f"Test weak signal event for {data['reason']}",
            timestamp=datetime.now(timezone.utc)
        )
        
        branch_id = manager.sink.ingest_unverified_entity(event)
        print(f"[{i+1}/{count}] Event for '{event.company_name}' -> Branch: {branch_id}")
    
    print("📥 Flushing sink to commit fragments...")
    manager.sink.flush()
    print("✅ Flush complete.")

if __name__ == "__main__":
    inject_weak_signals(15) # Create a bunch to ensure contention during resolve
