# pipelines/resolver/tier3_llm_judge.py
# Tier 3: LLM-as-Judge via Gemini for ambiguous entity pairs.

import os
import json
from typing import Optional, Dict, Any, List
from google import genai
from pydantic import BaseModel, Field
from models.account_event import AccountEvent

class Tier3Match(BaseModel):
    node_key: Optional[str] = Field(description="The node_key of the matching candidate, or null if no match is found with > 0.7 confidence.")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0.")
    reasoning: str = Field(description="Brief explanation of why this candidate was chosen or why no match was found.")

class LLMJudgeResolver:
    def __init__(self, client, api_key: Optional[str] = None):
        """
        :param client: MemgraphClient instance (to find candidates)
        :param api_key: Optional Gemini API key
        """
        self.client = client
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.model_name = "gemini-1.5-flash"
        self.merge_threshold = 0.70
        
        if self.api_key:
            self.genai_client = genai.Client(api_key=self.api_key)
        else:
            self.genai_client = None

    def resolve(self, event: AccountEvent) -> Optional[Dict[str, Any]]:
        """
        Attempt to resolve an event using Gemini LLM.
        """
        if not self.genai_client:
            return None

        # 1. Gather potential matches from the graph
        domain_matches = self.client.find_potential_matches(
            domain=event.company_domain,
            cik=event.cik_number
        )
        name_matches = self.client.find_by_name(event.company_name)
        
        all_matches = {m["node_key"]: m for m in domain_matches}
        for m in name_matches:
            if m["node_key"] not in all_matches:
                all_matches[m["node_key"]] = m
        
        if not all_matches:
            return None

        # 2. Prepare context for LLM
        candidates_str = ""
        for i, (key, m) in enumerate(all_matches.items()):
            candidates_str += f"\n[Candidate {i+1}]\n"
            candidates_str += f"node_key: {key}\n"
            candidates_str += f"company_name: {m['company_name']}\n"
            candidates_str += f"domain: {m.get('domain')}\n"
            candidates_str += f"cik_number: {m.get('cik_number')}\n"
            candidates_str += f"signals: {m.get('signals')}\n"

        prompt = f"""
You are an expert entity resolution judge. Your task is to determine if a new account event belongs to any of the existing account candidates in our knowledge graph.

New Event:
- Company Name: {event.company_name}
- Domain: {event.company_domain}
- CIK: {event.cik_number}
- Signals: {[s.value for s in event.risk_signals]}

Existing Candidates:
{candidates_str}

Compare the new event against each candidate. 
Look for subtle name variations, subsidiary relationships, or shared identifiers that weren't caught by deterministic rules.
If you find a candidate that is almost certainly the same company, return its node_key and your confidence.
If none of them match with at least 0.7 confidence, return null for node_key.
"""

        try:
            response = self.genai_client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": Tier3Match,
                }
            )
            
            match_data = response.parsed
            if not match_data:
                # Fallback if parsed fails
                match_data = json.loads(response.text)
            
            if match_data and match_data.node_key and match_data.confidence >= self.merge_threshold:
                # Retrieve the candidate details to get its company_name
                best_match = all_matches[match_data.node_key]
                return {
                    "node_key": match_data.node_key,
                    "company_name": best_match["company_name"],
                    "confidence": match_data.confidence,
                    "tier": 3,
                    "reasoning": match_data.reasoning
                }
        except Exception as e:
            # Silent fail for production
            pass
            
        return None
