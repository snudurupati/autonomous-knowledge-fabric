# tests/manual/seed_main.py
import os
import sys
from models.account_event import AccountEvent, EventSource, RiskSignal
from engine.omnigraph.client import OmnigraphClient

def seed_main():
    client = OmnigraphClient("http://127.0.0.1:8080")
    
    SEED_COMPANIES = [
        {"name": "apple", "domain": "apple.com", "account_id": "SF-001"},
        {"name": "microsoft", "domain": "microsoft.com", "account_id": "SF-002"},
        {"name": "tesla", "domain": "tesla.com", "account_id": "SF-003"},
        {"name": "jpmorgan", "domain": "jpmorgan.com", "account_id": "SF-004"},
        {"name": "walmart", "domain": "walmart.com", "account_id": "SF-005"},
    ]

    print(f"🚀 Seeding 5 base companies into crm-test main branch...")
    
    for company in SEED_COMPANIES:
        try:
            client.insert_account(
                name=company["name"],
                node_key=company["name"],
                risk_score=50,
                branch="main"
            )
            print(f"✅ Inserted '{company['name']}'")
        except Exception as e:
            print(f"❌ Failed to insert '{company['name']}': {e}")

if __name__ == "__main__":
    seed_main()
