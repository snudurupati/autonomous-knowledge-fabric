import requests
import json
from engine.omnigraph.client import OmnigraphClient

def check_duplicate_error():
    client = OmnigraphClient("http://127.0.0.1:8080")
    
    # Insert again with different name
    url = "http://127.0.0.1:8080/change?sync_branch=true"
    payload = {
        "query_source": "query q($n: String, $k: String) { insert Account { name: $n, node_key: $k, risk_score: 100 } }",
        "params": {"n": "New Name", "k": "dup_test"},
        "branch": "main"
    }
    
    res = requests.post(url, json=payload)
    print(f"Status: {res.status_code}")
    print(f"Body: {res.text}")

if __name__ == "__main__":
    check_duplicate_error()
