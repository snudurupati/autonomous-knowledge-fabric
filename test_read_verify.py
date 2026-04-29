from engine.omnigraph.client import OmnigraphClient

client = OmnigraphClient(base_url="http://127.0.0.1:8080")

print("--- Verifying Specific Account Read ---")
# This uses the get_account.gq file internally
result = client.get_account(node_key="test_123")

if result and result.get('rows'):
    account_data = result['rows'][0]
    print(f"✅ Success! Found Account: {account_data.get('a.name')}")
    print(f"   Risk Score: {account_data.get('a.risk_score')}")
    
    # Check if the data matches what we put in
    assert account_data.get('a.node_key') == 'test_123'
else:
    print("❌ Failed: Account not found or response format unexpected.")
    print(f"Raw Response: {result}")
