from engine.omnigraph.client import OmnigraphClient

client = OmnigraphClient(base_url="http://127.0.0.1:8080")

print("--- Inserting Account ---")
insert_resp = client.insert_account(name="Test Corp", node_key="test_123", risk_score=50)
print(insert_resp)

print("\n--- Reading Account ---")
read_resp = client.get_account(node_key="test_123")
print(read_resp)
