import requests
import os

class OmnigraphClient:
    def __init__(self, base_url="http://127.0.0.1:8080"):
        self.base_url = base_url
        # Resolve queries directory relative to this file's location
        # engine/omnigraph/client.py -> ../../queries
        self.queries_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../queries"))

    def _read_query(self, filename):
        path = os.path.join(self.queries_dir, filename)
        with open(path, "r") as f:
            return f.read()

    def _execute(self, endpoint, query_filename, params=None, branch="main"):
        """
        Executes a query from a file against the Omnigraph server.
        """
        query_source = self._read_query(query_filename)
        url = f"{self.base_url}/{endpoint}"
        payload = {
            "query_source": query_source,
            "branch": branch,
            "params": params or {}
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

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

    def get_account(self, node_key, branch="main"):
        """
        Reads an Account by node_key.
        """
        params = {
            "node_key": node_key
        }
        return self._execute("read", "get_account.gq", params, branch=branch)

if __name__ == "__main__":
    # Quick sanity check
    client = OmnigraphClient()
    print(f"Client initialized with queries from: {client.queries_dir}")
