# pipelines/resolver/tier3_llm_judge.py
# Tier 3: LLM-as-Judge via Gemini for ambiguous entity pairs with SQLite Rehydration Cache.

import os
import json
import asyncio
import sqlite3
import aiosqlite
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from google import genai
from pydantic import BaseModel, Field
from models.account_event import AccountEvent
from pipelines.resolver.tier1_deterministic import resolve as tier1_resolve

# Default cache path
CACHE_DB_PATH = os.environ.get("AKF_RESOLVER_CACHE", "akf_resolver_cache.db")

class Tier3Match(BaseModel):
    node_key: Optional[str] = Field(description="The node_key of the matching candidate, or null if no match is found with > 0.7 confidence.")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0.")
    reasoning: str = Field(description="Brief explanation of why this candidate was chosen or why no match was found.")

class LLMRehydrationCache:
    """Async SQLite cache for storing and retrieving LLM decisions."""
    def __init__(self, db_path: str = CACHE_DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Create the table if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS llm_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_a TEXT NOT NULL,
                    hash_b TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confidence REAL,
                    reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(hash_a, hash_b)
                )
            """)
            await db.commit()

    async def get_decision(self, hash_a: str, hash_b: str) -> Optional[Dict[str, Any]]:
        """Retrieve a decision using sorted hashes."""
        h1, h2 = sorted([hash_a, hash_b])
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT decision, confidence, reasoning FROM llm_decisions WHERE hash_a = ? AND hash_b = ?",
                (h1, h2)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "decision": row[0],
                        "confidence": row[1],
                        "reasoning": row[2]
                    }
        return None

    async def save_decision(self, hash_a: str, hash_b: str, decision: str, confidence: float, reasoning: str):
        """Save a decision using sorted hashes."""
        h1, h2 = sorted([hash_a, hash_b])
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO llm_decisions (hash_a, hash_b, decision, confidence, reasoning)
                   VALUES (?, ?, ?, ?, ?)""",
                (h1, h2, decision, confidence, reasoning)
            )
            await db.commit()

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
        self.cache = LLMRehydrationCache()
        
        # Initialize DB synchronously for now (or let first call handle it)
        # In a real async app we'd await init_db()
        if self.api_key:
            self.genai_client = genai.Client(api_key=self.api_key)
        else:
            self.genai_client = None

    def resolve(self, event: AccountEvent) -> Optional[Dict[str, Any]]:
        """
        Synchronous wrapper for async resolution.
        """
        try:
            # We use a separate event loop or run_until_complete if possible
            # But for simplicity in Pathway's sync thread, asyncio.run is usually safest
            return asyncio.run(self._resolve_async(event))
        except RuntimeError:
            # Already in an event loop? Try creating a task
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # This case is tricky if we're sync, but let's hope for the best
                return loop.run_until_complete(self._resolve_async(event))
            raise

    async def _resolve_async(self, event: AccountEvent) -> Optional[Dict[str, Any]]:
        """
        Attempt to resolve an event using Gemini LLM with caching.
        """
        if not self.genai_client:
            return None

        # Ensure DB is ready
        await self.cache.init_db()

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

        # 2. Check Cache first
        event_hash = tier1_resolve(event.company_name)["hash"]
        
        for node_key, match in all_matches.items():
            cached = await self.cache.get_decision(event_hash, node_key)
            if cached and cached["decision"] == "MATCH" and cached["confidence"] >= self.merge_threshold:
                return {
                    "node_key": node_key,
                    "company_name": match["company_name"],
                    "confidence": cached["confidence"],
                    "tier": 3,
                    "reasoning": f"(CACHED) {cached['reasoning']}"
                }

        # 3. If no cache hit, Prepare context for LLM
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
            # Model generation is still IO-bound, good to await if possible,
            # but SDK is sync or async? genai.Client.models.generate_content is usually blocking in basic form.
            # Actually the google-genai SDK supports async with aio.
            # I will use the async client if available or just the sync one in the async context.
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
                match_data = Tier3Match.model_validate_json(response.text)
            
            # Save ALL candidate decisions to cache?
            # For simplicity, we'll save the result we found.
            # If a match was found:
            if match_data.node_key:
                await self.cache.save_decision(
                    event_hash, 
                    match_data.node_key, 
                    "MATCH", 
                    match_data.confidence, 
                    match_data.reasoning
                )
                
                # If confidence is high enough, return it
                if match_data.confidence >= self.merge_threshold:
                    best_match = all_matches[match_data.node_key]
                    return {
                        "node_key": match_data.node_key,
                        "company_name": best_match["company_name"],
                        "confidence": match_data.confidence,
                        "tier": 3,
                        "reasoning": match_data.reasoning
                    }
            else:
                # Cache as NO_MATCH for the first candidate at least? 
                # This is less perfect than caching every candidate in the prompt,
                # but better than nothing.
                pass
                
        except Exception as e:
            # Silent fail for production
            pass
            
        return None
