# pipelines/resolver/tier2_graph_context.py
# Tier 2: 1-hop Memgraph neighbor query for relationship-aware entity resolution.

from typing import Optional, Dict, Any, List
from models.account_event import AccountEvent, RiskSignal
from pipelines.resolver.tier1_deterministic import normalize

class GraphContextResolver:
    def __init__(self, client):
        """
        :param client: MemgraphClient instance
        """
        self.client = client
        self.threshold_domain = 0.85
        self.threshold_cik = 1.0
        self.signal_weight_base = 0.40
        self.signal_weight_max = 0.65
        self.merge_threshold = 0.75

    def resolve(self, event: AccountEvent) -> Optional[Dict[str, Any]]:
        """
        Attempt to resolve an event to an existing node using graph context.
        Returns a dict with node_key and confidence if a match is found >= threshold.
        """
        # 1. Search for potential matches by domain and CIK (Deterministic/Strong)
        potential_matches = self.client.find_potential_matches(
            domain=event.company_domain,
            cik=event.cik_number
        )
        
        # 2. Add Name matches (Fuzzy/Substring) as secondary candidates
        name_matches = self.client.find_by_name(event.company_name)
        
        # Combine matches, keeping unique by node_key
        all_matches = {m["node_key"]: m for m in potential_matches}
        for m in name_matches:
            if m["node_key"] not in all_matches:
                all_matches[m["node_key"]] = m
        
        best_match = None
        max_confidence = 0.0
        
        for node_key, match in all_matches.items():
            confidence = 0.0
            
            # CIK match (1.0)
            if event.cik_number and match.get("cik_number") == event.cik_number:
                confidence = max(confidence, self.threshold_cik)
                
            # Domain match (0.85)
            if event.company_domain and match.get("domain") == event.company_domain:
                confidence = max(confidence, self.threshold_domain)
            
            # Shared signal logic (heuristic)
            # If name is similar AND they share risk signals, it's a contextual match.
            if confidence < self.merge_threshold:
                # Name similarity (base score for substring match)
                name_similarity = 0.0
                match_name_norm = normalize(match["company_name"])
                if event.company_name in match_name_norm or match_name_norm in event.company_name:
                    name_similarity = 0.3
                
                # Signal match (0.40 or 0.65)
                shared_signals = self._get_shared_signals(event.risk_signals, match.get("signals", []))
                signal_confidence = 0.0
                if shared_signals:
                    if len(shared_signals) == 1:
                        signal_confidence = self.signal_weight_base
                    else:
                        signal_confidence = self.signal_weight_max
                
                # Contextual confidence is additive if name is similar
                if name_similarity > 0:
                    confidence = max(confidence, name_similarity + signal_confidence)
                
            if confidence > max_confidence:
                max_confidence = confidence
                best_match = match
                
        if best_match and max_confidence >= self.merge_threshold:
            # Construct reasoning for Tier-2
            match_type = "CIK" if event.cik_number and best_match.get("cik_number") == event.cik_number else \
                         "Domain" if event.company_domain and best_match.get("domain") == event.company_domain else \
                         "Contextual (Name + Signals)"
            
            return {
                "node_key": best_match["node_key"],
                "company_name": best_match["company_name"],
                "confidence": max_confidence,
                "tier": 2,
                "reasoning": f"Match found via {match_type}"
            }
            
        return None

    def _get_shared_signals(self, event_signals: List[RiskSignal], node_signals: List[str]) -> List[str]:
        event_sig_vals = {s.value for s in event_signals}
        return [s for s in node_signals if s in event_sig_vals]
