import unittest
import uuid
import requests
from engine.omnigraph.client import OmnigraphClient

class TestOmnigraphTransactions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We assume the server is running on localhost:8080 as per the previous setup
        cls.client = OmnigraphClient(base_url="http://127.0.0.1:8080")

    def test_atomic_rollback_on_partial_failure(self):
        """
        Verifies that a multi-statement mutation rolls back completely if any 
        statement fails (e.g., due to a schema violation).
        """
        unique_key = f"tx_rollback_test_{uuid.uuid4().hex[:8]}"
        event_id = f"evt_{uuid.uuid4().hex[:8]}"
        
        print(f"\n[Test] Attempting atomic mutation with 'poison pill' for account: {unique_key}")
        
        # We provide valid data for the Account part, 
        # but 'None' for the required 'source' field of the AccountEvent part.
        # This should cause the transaction to fail during execution of the second statement.
        with self.assertRaises(requests.exceptions.HTTPError) as cm:
            self.client.ingest_event_complete(
                name="Rollback Test Corp",
                node_key=unique_key,
                risk_score=99,
                event_id=event_id,
                source=None,  # <--- The Poison Pill: Required field cannot be None
                timestamp="2026-05-14",
                risk_signals=["POISON_PILL"],
                raw_text="This transaction should roll back."
            )
        
        error_resp = cm.exception.response
        print(f"[Test] Caught expected error: {error_resp.status_code} - {error_resp.text.strip()}")
        self.assertEqual(error_resp.status_code, 400, "Expected 400 Bad Request for schema violation")

        # ASSERTION: The valid part of the transaction (the Account insert) must NOT have been persisted.
        print(f"[Test] Verifying that account {unique_key} was NOT created...")
        get_resp = self.client.get_account(unique_key)
        rows = get_resp.get("rows", [])
        
        self.assertEqual(len(rows), 0, f"Failure: Account {unique_key} was persisted despite transaction failure! Atomicity violated.")
        print(f"[Test] Success: Account {unique_key} is not in the graph. Transaction rolled back correctly.")

    def test_atomic_success(self):
        """
        Verifies that a valid multi-statement mutation commits correctly.
        """
        unique_key = f"tx_success_test_{uuid.uuid4().hex[:8]}"
        event_id = f"evt_{uuid.uuid4().hex[:8]}"
        
        print(f"\n[Test] Attempting atomic mutation with valid data for account: {unique_key}")
        
        resp = self.client.ingest_event_complete(
            name="Success Test Corp",
            node_key=unique_key,
            risk_score=10,
            event_id=event_id,
            source="UNIT_TEST",
            timestamp="2026-05-14",
            risk_signals=["SUCCESS_SIGNAL"],
            raw_text="This transaction should succeed."
        )
        
        self.assertIn("affected_nodes", resp)
        self.assertGreaterEqual(resp["affected_nodes"], 2) # Account and Event
        
        # Verify persistence
        get_resp = self.client.get_account(unique_key)
        rows = get_resp.get("rows", [])
        self.assertEqual(len(rows), 1, f"Failure: Account {unique_key} was not persisted.")
        self.assertEqual(rows[0].get("a.name"), "Success Test Corp")
        print(f"[Test] Success: Atomic transaction committed correctly.")

if __name__ == "__main__":
    unittest.main()
