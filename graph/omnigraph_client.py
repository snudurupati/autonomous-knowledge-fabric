# graph/omnigraph_client.py
# High-level wrapper around OmnigraphClient to maintain compatibility with legacy Memgraph calls.

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from engine.omnigraph.client import OmnigraphClient
from engine.omnigraph.ingestion_sink import OmnigraphSink
from scoring.account_health import calculate_risk_score, get_risk_level
from pipelines.resolver.tier1_deterministic import resolve as tier1_resolve
from models.account_event import AccountEvent

logger = logging.getLogger(__name__)

class OmnigraphClientWrapper:
    """
    A high-level wrapper for OmnigraphClient that provides an interface
    similar to the legacy MemgraphClient.
    """
    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.client = OmnigraphClient(base_url=base_url)
        self.sink = OmnigraphSink(server_url=base_url)

    def upsert_account(self, event: AccountEvent) -> str:
        """Upsert an account node. Returns the node_key."""
        signals = [{"name": s.value, "timestamp": event.timestamp.isoformat()} for s in event.risk_signals]
        risk_score = calculate_risk_score(signals)
        self.client.insert_account(
            name=event.company_name,
            node_key=event.company_name,
            risk_score=risk_score
        )
        return event.company_name

    def upsert_event(self, event: AccountEvent) -> None:
        """Upsert an event using the OmnigraphSink."""
        self.sink.ingest_event(event)

    def get_account_context(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Return structured account context for LLM agent consumption."""
        # Omnigraph uses node_key as the primary identifier.
        node_key = company_name 
        
        try:
            resp = self.client.get_account_context(node_key=node_key)
            rows = resp.get("rows", [])
            if not rows:
                return None

            # Aggregate rows
            first_row = rows[0]
            context = {
                "company_name": first_row.get("a.name"),
                "cik_number": None, # Placeholder for now
                "last_updated": "unknown",
                "total_events": len(rows),
                "recent_events": [],
                "risk_signals": [],
                "risk_signal_details": [],
                "risk_score": first_row.get("a.risk_score"),
                "risk_level": get_risk_level(first_row.get("a.risk_score", 0)),
                "context_age_seconds": 0
            }

            seen_events = set()
            for row in rows:
                event_id = row.get("e.event_id")
                if event_id and event_id not in seen_events:
                    seen_events.add(event_id)
                    context["recent_events"].append(row.get("e.raw_text"))
                    
                    signals = row.get("e.risk_signals", [])
                    ts = row.get("e.timestamp")
                    for s in signals:
                        if s not in context["risk_signals"]:
                            context["risk_signals"].append(s)
                            context["risk_signal_details"].append({
                                "name": s,
                                "timestamp": ts
                            })

            return context
        except Exception as e:
            logger.error(f"Error fetching account context for {company_name}: {e}")
            return None

    def get_high_risk_accounts(self, min_score: int = 70) -> List[Dict[str, Any]]:
        """Return accounts with their risk signals and calculated scores."""
        try:
            resp = self.client.get_high_risk_accounts(min_score=min_score)
            rows = resp.get("rows", [])
            
            results = []
            for row in rows:
                score = row.get("a.risk_score", 0)
                results.append({
                    "company": row.get("a.name"),
                    "score": score,
                    "level": get_risk_level(score),
                    "signals": [] # We don't have signals in the high_risk query yet
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching high risk accounts: {e}")
            return []

    def search_accounts(self, query: str) -> List[Dict[str, Any]]:
        """Search for accounts using BM25 text search with a client-side substring fallback."""
        try:
            # Try Omnigraph's text search first
            resp = self.client._execute("read", "search.gq", {"query": query})
            rows = resp.get("rows", [])
            
            if rows:
                results = []
                for row in rows:
                    results.append({
                        "company_name": row.get("a.name"),
                        "node_key": row.get("a.node_key"),
                        "risk_score": row.get("a.risk_score", 0)
                    })
                return results
            
            # Fallback: Client-side partial matching if no direct results
            # (Fetching all accounts is efficient in Omnigraph due to Lance/S3 memory mapping)
            all_accounts = self.get_high_risk_accounts(min_score=0)
            query_lower = query.lower()
            matches = []
            for acc in all_accounts:
                if query_lower in acc['company'].lower():
                    matches.append({
                        "company_name": acc['company'],
                        "node_key": acc['company'], # node_key is usually the name in this project
                        "risk_score": acc['score']
                    })
            
            # Sort matches by length (shorter names often closer to exact match)
            matches.sort(key=lambda x: len(x['company_name']))
            return matches[:10]
            
        except Exception as e:
            logger.error(f"Error searching accounts: {e}")
            return []

    def find_potential_matches(self, domain: str | None = None, cik: str | None = None) -> List[Dict[str, Any]]:
        """Placeholder for Tier-2 resolution matches."""
        # Omnigraph queries would need to be updated to support domain/cik filtering
        return []

    def find_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Placeholder for name-based matching."""
        return self.search_accounts(name)

    def get_platform_stats(self) -> Dict[str, int]:
        """Return global platform metrics: total accounts, events, and relationships."""
        stats = {"accounts": 0, "events": 0, "relationships": 0}
        try:
            # Omnigraph 0.4.1 prefers independent queries for global counts to avoid join overhead
            acc_resp = self.client._execute("read", "count_accounts.gq")
            if acc_resp.get("rows"):
                stats["accounts"] = acc_resp["rows"][0].get("c", 0)
                
            evt_resp = self.client._execute("read", "count_events.gq")
            if evt_resp.get("rows"):
                stats["events"] = evt_resp["rows"][0].get("c", 0)
                
            rel_resp = self.client._execute("read", "count_relationships.gq")
            if rel_resp.get("rows"):
                stats["relationships"] = rel_resp["rows"][0].get("c", 0)
                
            return stats
        except Exception as e:
            logger.error(f"Error fetching platform stats: {e}")
            return stats
