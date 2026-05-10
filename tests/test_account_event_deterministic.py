import unittest
from datetime import datetime, timezone
from models.account_event import AccountEvent, EventSource

class TestAccountEventDeterministicID(unittest.TestCase):
    
    def test_explicit_event_id(self):
        """If an explicit event_id is provided, it should be used."""
        event = AccountEvent(
            event_id="explicit-123",
            source=EventSource.SEC_EDGAR,
            company_name="Test Corp",
            raw_text="Test filing"
        )
        self.assertEqual(event.event_id, "explicit-123")

    def test_deterministic_id_generation(self):
        """If no event_id is provided, identical events should generate identical IDs."""
        event1 = AccountEvent(
            source=EventSource.SEC_EDGAR,
            company_name="Test Corp",
            raw_text="Test filing",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        
        # Exact same source, company, and text, but different timestamp
        event2 = AccountEvent(
            source=EventSource.SEC_EDGAR,
            company_name="Test Corp",
            raw_text="Test filing",
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        
        # ID should be generated
        self.assertIsNotNone(event1.event_id)
        # IDs should be identical despite different timestamps (they are the same filing)
        self.assertEqual(event1.event_id, event2.event_id)

    def test_different_events_different_ids(self):
        """Different events should generate different IDs."""
        event1 = AccountEvent(
            source=EventSource.SEC_EDGAR,
            company_name="Test Corp",
            raw_text="Test filing A"
        )
        
        event2 = AccountEvent(
            source=EventSource.SEC_EDGAR,
            company_name="Test Corp",
            raw_text="Test filing B" # Different text
        )
        
        self.assertNotEqual(event1.event_id, event2.event_id)

if __name__ == '__main__':
    unittest.main()
