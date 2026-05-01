import requests
import os

class OmnigraphClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        # Resolve queries directory relative to this file's location
        # engine/omnigraph/client.py -> ../../queries
        self.queries_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../queries"))

    def _read_query(self, filename):
        path = os.path.join(self.queries_dir, filename)
        with open(path, "r") as f:
            return f.read()

    def _execute(self, endpoint, query_filename, params=None, branch="main", snapshot_id=None):
        """
        Executes a query from a file against the Omnigraph server.
        Supports snapshot-pinned reads via the snapshot_id parameter in the payload.
        Includes automatic retry for 409 Conflict (version drift) and forces branch sync.
        """
        query_source = self._read_query(query_filename)
        
        payload = {
            "query_source": query_source,
            "params": params or {}
        }
        
        # If snapshot_id is provided, use it and omit branch
        if snapshot_id:
            payload["snapshot"] = snapshot_id
        elif branch:
            payload["branch"] = branch
        
        max_retries = 3
        retry_delay = 0.5
        
        # We add ?sync_branch=true to force the server to advance its pinned head
        # for this branch. This is the fix for the "version drift" error.
        url = f"{self.base_url}/{endpoint}?sync_branch=true"
        
        for attempt in range(max_retries + 1):
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                return response.json()
            
            # 409 Conflict indicates version drift. We retry after a short delay.
            if response.status_code == 409 and attempt < max_retries:
                import time
                time.sleep(retry_delay * (attempt + 1))
                continue
                
            # If we reach here, it's either not a 409 or we've exhausted retries
            raise requests.exceptions.HTTPError(
                f"{response.status_code} Client Error: {response.reason} for url: {response.url}\nBody: {response.text}", 
                response=response
            )

    def insert_account(self, name, node_key, risk_score, branch="main"):
        """
        Inserts an Account node.
        """
        params = {
            "name": name,
            "node_key": node_key,
            "risk_score": risk_score
        }
        return self._execute("change", "insert_account.gq", params, branch=branch)

    def insert_event(self, event_id, source, timestamp, risk_signals=None, raw_text=None, branch="main"):
        """
        Inserts an AccountEvent node.
        """
        params = {
            "event_id": event_id,
            "source": source,
            "timestamp": timestamp,
            "risk_signals": risk_signals or [],
            "raw_text": raw_text or ""
        }
        return self._execute("change", "insert_event.gq", params, branch=branch)

    def link_account_event(self, account_key, event_id, branch="main"):
        """
        Links an Account to an AccountEvent via HAS_EVENT edge.
        """
        params = {
            "account": account_key,
            "event": event_id
        }
        return self._execute("change", "link_account_event.gq", params, branch=branch)

    def ingest_event_complete(self, name, node_key, risk_score, event_id, source, timestamp, risk_signals=None, raw_text=None, branch="main"):
        """
        Ingests an account, an event, and the link between them in a single transactional request.
        """
        params = {
            "name": name,
            "node_key": node_key,
            "risk_score": risk_score,
            "event_id": event_id,
            "source": source,
            "timestamp": timestamp,
            "risk_signals": risk_signals or [],
            "raw_text": raw_text or ""
        }
        return self._execute("change", "ingest_event_complete.gq", params, branch=branch)

    def get_account(self, node_key, branch="main", snapshot_id=None):
        """
        Reads an Account by node_key.
        """
        params = {
            "node_key": node_key
        }
        return self._execute("read", "get_account.gq", params, branch=branch, snapshot_id=snapshot_id)

    def get_account_context(self, node_key, branch="main", snapshot_id=None):
        """
        Reads an Account and its associated context (AccountEvents).
        """
        params = {
            "node_key": node_key
        }
        return self._execute("read", "get_account_context.gq", params, branch=branch, snapshot_id=snapshot_id)

    def get_high_risk_accounts(self, min_score=70, branch="main", snapshot_id=None):
        """
        Reads all accounts with a risk score greater than or equal to min_score.
        """
        params = {
            "min_score": min_score
        }
        return self._execute("read", "get_high_risk_accounts.gq", params, branch=branch, snapshot_id=snapshot_id)

    def get_latest_snapshot_id(self):
        """
        Fetches the latest graph_commit_id from the server.
        """
        response = requests.get(f"{self.base_url}/commits")
        response.raise_for_status()
        commits = response.json().get("commits", [])
        if commits:
            # Commits are returned in chronological order, get the last one
            return commits[-1]["graph_commit_id"]
        return None

if __name__ == "__main__":
    # Quick sanity check
    client = OmnigraphClient()
    print(f"Client initialized with queries from: {client.queries_dir}")
