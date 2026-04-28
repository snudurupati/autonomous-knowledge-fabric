import unittest
import os
from engine.omnigraph.client import OmnigraphClient

class TestOmnigraphClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = OmnigraphClient(base_url="http://127.0.0.1:8080")

    def test_insert_and_get_account(self):
        # Data for the test account
        name = "Acme Corp"
        node_key = "acme_123"
        risk_score = 42

        # 1. Insert the account
        print(f"\nInserting account: {node_key}")
        insert_resp = self.client.insert_account(name, node_key, risk_score)
        # Check if insert was successful
        # Successful insertion returns affected_nodes count
        self.assertIn("affected_nodes", insert_resp)
        self.assertGreater(insert_resp["affected_nodes"], 0)

        # 2. Retrieve the account
        print(f"Retrieving account: {node_key}")
        get_resp = self.client.get_account(node_key)
        print(f"Full Response: {get_resp}")
        
        # Omnigraph /read returns a list of rows
        results = get_resp.get("rows", [])
        self.assertGreater(len(results), 0, "No results returned from get_account")
        
        account = results[0]
        # Omnigraph returns keys in 'alias.property' format (no $)
        self.assertEqual(account.get("a.name"), name)
        self.assertEqual(account.get("a.node_key"), node_key)
        self.assertEqual(account.get("a.risk_score"), risk_score)
        print("Success: Account inserted and retrieved correctly.")

if __name__ == "__main__":
    unittest.main()
