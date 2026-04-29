import logging
import uuid
import requests
import os
import time
import urllib.parse
from typing import Dict, Any, Optional
from observability.telemetry import latency_tracker
from models.account_event import AccountEvent
from engine.omnigraph.client import OmnigraphClient
from scoring.account_health import calculate_risk_score

# Configure logging for observability and benchmarking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OmnigraphSink:
    """
    Omnigraph Ingestion Sink (Sprint 17/18)
    
    Manages ingestion of AccountEvents into Omnigraph.
    Uses OmnigraphClient for Schema-as-Code compliant mutations.
    """
    def __init__(self, 
                 server_url: Optional[str] = None, 
                 main_branch: str = "main",
                 use_buffering: bool = False):
        
        self.server_url = (server_url or 
                           os.getenv("OMNIGRAPH_SERVER_URL", "http://localhost:8080"))
        self.main_branch = main_branch
        self.use_buffering = use_buffering
        
        # Initialize the specialized Omnigraph Client
        self.client = OmnigraphClient(self.server_url)
        
        logger.info(f"Initialized OmnigraphSink. Server: {self.server_url}, Main Branch: {self.main_branch}, Buffering: {self.use_buffering}")

    def ingest_unverified_entity(self, event: AccountEvent) -> bool:
        """
        Maps an AccountEvent to an Account node upsert.
        Calculates risk score and uses Omnigraph's @key for deterministic merging.
        """
        return self.ingest_event(event)

    def ingest_event(self, event: AccountEvent) -> bool:
        """
        Maps an AccountEvent to an Account node upsert.
        Calculates risk score and uses Omnigraph's @key for deterministic merging.
        """
        start_time = time.monotonic()
        
        company_name = event.company_name
        source = event.source.value
            
        # Record received for latency tracking
        latency_tracker.record_event_received(event.event_id, source, company_name)
        
        # 1. Calculate Risk Score from signals
        signals = [{"name": s.value, "timestamp": event.timestamp.isoformat()} for s in event.risk_signals]
        risk_score = calculate_risk_score(signals)
        
        # 2. Determine target branch
        target_branch = self.main_branch
        if self.use_buffering:
            target_branch = f"fragment-{uuid.uuid4().hex[:8]}"
            # Create branch if buffering enabled
            requests.post(f"{self.server_url}/branches", json={
                "name": target_branch,
                "base": self.main_branch
            }).raise_for_status()
        
        try:
            # 3. Upsert the Account node using OmnigraphClient.insert_account
            # The @key (node_key) ensures that this updates the existing account if it exists.
            self.client.insert_account(
                name=company_name,
                node_key=company_name, 
                risk_score=risk_score,
                branch=target_branch
            )

            # 3.1 Insert the AccountEvent node
            self.client.insert_event(
                event_id=event.event_id,
                source=source,
                timestamp=event.timestamp.date().isoformat(),
                risk_signals=[s.value for s in event.risk_signals],
                raw_text=event.raw_text,
                branch=target_branch
            )

            # 3.2 Link Account -> AccountEvent
            self.client.link_account_event(
                account_key=company_name,
                event_id=event.event_id,
                branch=target_branch
            )
            
            # 4. Post-Ingestion Verification (Read back)
            verification = self.client.get_account(company_name, branch=target_branch)
            rows = verification.get("rows", [])
            if rows:
                state = rows[0]
                logger.info(f"POST_INGEST_VERIFICATION key='{company_name}' risk_score={state.get('a.risk_score')} branch={target_branch}")
            
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.info(f"INGEST_SUCCESS entity='{company_name}' score={risk_score} latency_ms={latency_ms:.1f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ingest entity '{company_name}': {e}")
            return False

    def evaluate_and_merge(self, branch_id: str, evidence_score: int, threshold: int = 70) -> bool:
        """
        Merges a side-branch into main if threshold met.
        """
        if branch_id == self.main_branch:
            return True
            
        start_time = time.monotonic()
        try:
            if evidence_score > threshold:
                merge_resp = requests.post(f"{self.server_url}/branches/merge", json={
                    "source": branch_id,
                    "target": self.main_branch,
                    "strategy": "fast-forward"
                })
                merge_resp.raise_for_status()
                logger.info(f"MERGE_SUCCESS branch={branch_id} latency_ms={(time.monotonic() - start_time)*1000:.1f}")
                return True
            else:
                requests.delete(f"{self.server_url}/branches/{branch_id}").raise_for_status()
                logger.warning(f"MERGE_DROPPED branch={branch_id}")
                return False
        except Exception as e:
            logger.error(f"Merge failed for {branch_id}: {e}")
            return False

if __name__ == "__main__":
    from models.account_event import EventSource, RiskSignal
    # Test simulation
    sink = OmnigraphSink(use_buffering=False) # Writing to main for verification
    
    test_evt = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme Corp",
        risk_signals=[RiskSignal.CRITICAL_SUPPORT],
        raw_text="Support case escalated."
    )
    
    print("\n--- Phase 1: Ingesting Initial Event ---")
    sink.ingest_event(test_evt)
    
    print("\n--- Phase 2: Updating with Higher Risk ---")
    test_evt.risk_signals.append(RiskSignal.TAKEOVER_BID)
    sink.ingest_event(test_evt)
