# tests/manual/test_direct_main_insert.py
import requests
import os
import sys
from engine.omnigraph.client import OmnigraphClient

def test_insert():
    client = OmnigraphClient("http://127.0.0.1:8080")
    print("🚀 Attempting direct insert to 'main' branch...")
    try:
        # Insert a company that definitely doesn't exist
        res = client.insert_account(
            name="OmniCorp Test",
            node_key="omnicorp_test",
            risk_score=10,
            branch="main"
        )
        print(f"✅ Success! Response: {res}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    test_insert()
