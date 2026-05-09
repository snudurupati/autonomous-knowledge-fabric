import unittest
from unittest.mock import patch, MagicMock
import requests
from pipelines.batch_resolver import execute_decisions_safe, BatchResolutionItem

class TestResolverRebase(unittest.TestCase):
    
    @patch("requests.post")
    @patch("requests.delete")
    @patch("time.sleep") # Speed up tests
    def test_execute_decisions_rebase_on_409(self, mock_sleep, mock_delete, mock_post):
        """
        Verify that execute_decisions_safe correctly triggers a rebase
        when it encounters a 409 Conflict during merge.
        """
        server_url = "http://test-server:8080"
        decisions = [
            BatchResolutionItem(branch_id="fragment-123", is_match=True, reasoning="Exact match")
        ]
        
        # Setup Mock Sequence:
        # 1. First Merge Attempt (fragment -> main) -> 409 Conflict
        mock_409 = MagicMock()
        mock_409.status_code = 409
        mock_409.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_409)
        
        # 2. Rebase Attempt (main -> fragment) -> 200 OK
        mock_200 = MagicMock()
        mock_200.status_code = 200
        
        # 3. Second Merge Attempt (fragment -> main) -> 200 OK
        
        mock_post.side_effect = [mock_409, mock_200, mock_200]
        mock_delete.return_value = mock_200
        
        # Execute
        stats = execute_decisions_safe(server_url, decisions)
        
        # Assertions
        self.assertEqual(stats["merged"], 1)
        self.assertEqual(stats["failed"], 0)
        
        # Check call sequence:
        self.assertEqual(mock_post.call_count, 3)
        
        # Call 1: Original Merge
        args1, json1 = mock_post.call_args_list[0][0], mock_post.call_args_list[0][1]["json"]
        self.assertIn("/branches/merge", args1[0])
        self.assertEqual(json1["source"], "fragment-123")
        self.assertEqual(json1["target"], "main")
        
        # Call 2: Rebase (Source is 'main')
        args2, json2 = mock_post.call_args_list[1][0], mock_post.call_args_list[1][1]["json"]
        self.assertIn("/branches/merge", args2[0])
        self.assertEqual(json2["source"], "main") # CRITICAL: Main is the source for rebase
        self.assertEqual(json2["target"], "fragment-123")
        
        # Call 3: Retry Merge
        args3, json3 = mock_post.call_args_list[2][0], mock_post.call_args_list[2][1]["json"]
        self.assertEqual(json3["source"], "fragment-123")
        self.assertEqual(json3["target"], "main")

if __name__ == "__main__":
    unittest.main()
