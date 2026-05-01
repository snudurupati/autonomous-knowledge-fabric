import unittest
from unittest.mock import patch, MagicMock
import requests
from engine.omnigraph.client import OmnigraphClient
from pipelines.routing import OmnigraphRoutingManager
from models.account_event import AccountEvent, EventSource

class TestFastPath409Fix(unittest.TestCase):
    def setUp(self):
        self.client = OmnigraphClient(base_url="http://test-server:8080")

    @patch("requests.post")
    def test_client_retries_on_409(self, mock_post):
        # Setup mock to return 409 twice, then 200
        mock_response_409 = MagicMock()
        mock_response_409.status_code = 409
        mock_response_409.reason = "Conflict"
        mock_response_409.text = '{"error": "version drift"}'
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"affected_nodes": 1}

        mock_post.side_effect = [mock_response_409, mock_response_409, mock_response_200]

        # Execute call
        result = self.client.insert_account("Test Corp", "test_123", 50)

        # Assertions
        self.assertEqual(result["affected_nodes"], 1)
        self.assertEqual(mock_post.call_count, 3)
        
        # Verify sync_branch=true is in the URL
        args, kwargs = mock_post.call_args
        self.assertIn("sync_branch=true", args[0])

    @patch("requests.post")
    def test_client_exhausts_retries_on_409(self, mock_post):
        # Setup mock to always return 409
        mock_response_409 = MagicMock()
        mock_response_409.status_code = 409
        mock_response_409.reason = "Conflict"
        mock_response_409.text = '{"error": "version drift"}'
        mock_response_409.url = "http://test-server:8080/change?sync_branch=true"
        
        mock_post.return_value = mock_response_409

        # Execute call and expect exception after 4 attempts (1 initial + 3 retries)
        with self.assertRaises(requests.exceptions.HTTPError) as cm:
            self.client.insert_account("Test Corp", "test_123", 50)
        
        self.assertEqual(cm.exception.response.status_code, 409)
        self.assertEqual(mock_post.call_count, 4)

    def test_routing_fast_path_logic(self):
        # Verify that routing manager correctly identifies strong signals and hits main
        mock_sink = MagicMock()
        # Mock use_buffering to be True initially
        mock_sink.use_buffering = True
        
        manager = OmnigraphRoutingManager(sink=mock_sink)
        
        event = AccountEvent(
            source=EventSource.SEC_EDGAR,
            company_name="Fast Corp",
            cik_number="CIK123", # Strong signal
            raw_text="test"
        )
        
        # We need to track the value of use_buffering during the call
        buffering_states = []
        def capture_ingest_event(evt):
            buffering_states.append(mock_sink.use_buffering)
            return "main"
        
        mock_sink.ingest_event.side_effect = capture_ingest_event
        
        promoted = manager.process_event(event)
        
        self.assertTrue(promoted)
        self.assertEqual(mock_sink.ingest_event.call_count, 1)
        self.assertIn(False, buffering_states, "Fast-path should have disabled buffering")
        self.assertTrue(mock_sink.use_buffering, "Buffering should have been restored")

if __name__ == "__main__":
    unittest.main()
