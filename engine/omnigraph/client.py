import logging
import requests
import os
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pipelines.resolver.tier1_deterministic import resolve as tier1_resolve
from scoring.account_health import calculate_risk_score, get_risk_level

logger = logging.getLogger(__name__)

class OmnigraphClient:
    """
    Omnigraph Read Client (Sprint 18)
    
    Replaces the legacy MemgraphClient. 
    Supports snapshot-pinned reads for immutable agent context.
    """
    def __init__(self, 
                 server_url: Optional[str] = None,
                 main_branch: str = "main"):
        
        self.server_url = (server_url or 
                           os.getenv("OMNIGRAPH_SERVER_URL", "http://127.0.0.1:8080"))
        self.main_branch = main_branch
        logger.info(f"Initialized OmnigraphClient. Server: {self.server_url}")

    def _query(self, query: str, parameters: Dict[str, Any] = None, snapshot_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Executes a Cypher-like query on the Omnigraph server.
        If snapshot_id is provided, the read is pinned to that specific version.
        """
        payload = {
            "query": query,
            "parameters": parameters or {}
        }
        
        if snapshot_id:
            payload["snapshot"] = snapshot_id
        else:
            payload["branch"] = self.main_branch
            
        try:
            resp = requests.post(f"{self.server_url}/query", json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Assuming the response format is a list of dictionaries (rows)
            return data.get("results", [])
        except Exception as e:
            logger.error(f"Omnigraph query failed: {e}")
            return []

    def get_latest_snapshot(self) -> Optional[str]:
        """Returns the latest snapshot ID for the main branch."""
        try:
            resp = requests.get(f"{self.server_url}/snapshots?branch={self.main_branch}")
            resp.raise_for_status()
            snapshots = resp.json()
            if snapshots:
                # Assuming they are ordered by time, latest first
                return snapshots[0].get("id")
        except Exception as e:
            logger.error(f"Failed to fetch snapshots: {e}")
        return None

    def get_account_context(self, company_name: str, snapshot_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Return structured account context for LLM agent consumption.
        Pinned to snapshot_id if provided.
        """
        resolved = tier1_resolve(company_name)
        node_key = resolved["hash"]
        
        # Omnigraph uses Cypher for its underlying engine
        query = """
        MATCH (a:Account)
        WHERE a.node_key = $key OR a.name = $name
        OPTIONAL MATCH (a)<-[:FILED]-(e:Event)
        OPTIONAL MATCH (a)-[r:HAS_SIGNAL]->(s:RiskSignal)
        RETURN 
            a.name AS company,
            a.cik_number AS cik,
            a.last_updated AS last_updated,
            COLLECT(DISTINCT {text: e.raw_text, ts: e.timestamp}) AS events,
            COLLECT(DISTINCT {name: s.name, timestamp: r.timestamp}) AS risk_signals
        """
        
        rows = self._query(query, {"key": node_key, "name": company_name}, snapshot_id=snapshot_id)
        
        if not rows or rows[0].get("company") is None:
            return None
            
        row = rows[0]
        
        # Format events
        sorted_events = sorted(row.get("events", []), key=lambda x: x.get("ts", ""), reverse=True)
        recent_texts = [e["text"] for e in sorted_events[:3] if e.get("text")]
        
        # Calculate scores
        raw_signals = [s for s in row.get("risk_signals", []) if s.get("name")]
        risk_score = calculate_risk_score(raw_signals)
        
        # Age calculation
        last_updated = row.get("last_updated")
        context_age_seconds = 0
        if last_updated:
            try:
                # Remove Z and handle offsets
                ts = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                context_age_seconds = int((datetime.now(timezone.utc) - ts).total_seconds())
            except Exception:
                pass

        return {
            "company_name": row["company"],
            "cik_number": row.get("cik"),
            "last_updated": last_updated,
            "total_events": len(row.get("events", [])),
            "recent_events": recent_texts,
            "risk_signals": [s["name"] for s in raw_signals],
            "risk_signal_details": raw_signals,
            "risk_score": risk_score,
            "risk_level": get_risk_level(risk_score),
            "context_age_seconds": context_age_seconds
        }

    def get_high_risk_accounts(self, snapshot_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return accounts with their risk signals and calculated scores."""
        query = """
        MATCH (a:Account)
        OPTIONAL MATCH (a)-[r:HAS_SIGNAL]->(s:RiskSignal)
        RETURN 
            a.name AS company,
            COLLECT(DISTINCT {name: s.name, timestamp: r.timestamp}) AS risk_signals
        """
        
        rows = self._query(query, snapshot_id=snapshot_id)
        results = []
        
        for row in rows:
            raw_signals = [s for s in row.get("risk_signals", []) if s.get("name")]
            score = calculate_risk_score(raw_signals)
            if score > 0:
                results.append({
                    "company": row["company"],
                    "score": score,
                    "level": get_risk_level(score),
                    "signals": [s["name"] for s in raw_signals]
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:20]

if __name__ == "__main__":
    # Quick test
    client = OmnigraphClient()
    snapshot = client.get_latest_snapshot()
    print(f"Latest Snapshot: {snapshot}")
    
    context = client.get_account_context("apple", snapshot_id=snapshot)
    if context:
        print(f"Risk Score for Apple: {context['risk_score']}")
