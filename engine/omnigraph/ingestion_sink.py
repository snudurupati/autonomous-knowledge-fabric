import logging
import uuid
import requests
import boto3
import os
import time
from typing import Dict, Any, Optional
from observability.telemetry import latency_tracker
from models.account_event import AccountEvent

# Configure logging for observability and benchmarking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OmnigraphSink:
    """
    Omnigraph Ingestion Sink (Sprint 17)
    
    Replaces the legacy in-memory GhostNodeManager with native side-branch buffering.
    Each unverified entity fragment is stored in its own branch until verified.
    """
    def __init__(self, 
                 server_url: Optional[str] = None, 
                 s3_endpoint: Optional[str] = None,
                 main_branch: str = "main"):
        
        self.server_url = (server_url or 
                           os.getenv("OMNIGRAPH_SERVER_URL", "http://127.0.0.1:8080"))
        self.main_branch = main_branch
        
        # S3 configuration via environment variables for S3-Native storage
        self.s3_endpoint = (s3_endpoint or 
                            os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000"))
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
        self.region = os.getenv("AWS_REGION", "us-east-1")

        # S3 client pointed at local RustFS or production S3
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.s3_endpoint,
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )
        logger.info(f"Initialized OmnigraphSink. Server: {self.server_url}, S3: {self.s3_endpoint}")

    def ingest_unverified_entity(self, entity_data: Any) -> Optional[str]:
        """
        Takes an unverified entity fragment, creates a headless side-branch, 
        and writes the fragment there instead of holding it in memory.
        
        Supports both Dict and AccountEvent objects.
        """
        start_time = time.monotonic()
        
        if isinstance(entity_data, AccountEvent):
            event_id = entity_data.event_id
            company_name = entity_data.company_name
            source = entity_data.source.value
        else:
            event_id = entity_data.get("event_id", str(uuid.uuid4()))
            company_name = entity_data.get("company_name", "Unknown")
            source = entity_data.get("source", "UNKNOWN")
            
        # Record received for latency tracking
        latency_tracker.record_event_received(event_id, source, company_name)
        
        # 1. Create a unique side-branch (headless branch) for this entity fragment
        branch_id = f"fragment/{uuid.uuid4().hex[:8]}"
        
        try:
            # Create branch in Omnigraph
            resp = requests.post(f"{self.server_url}/branches", json={
                "name": branch_id,
                "base": self.main_branch
            })
            resp.raise_for_status()
            
            # 2. Write the entity fragment to the new branch
            # We use the /query endpoint to execute a CREATE mutation
            query_resp = requests.post(f"{self.server_url}/query", json={
                "branch": branch_id,
                "query": "CREATE (a:Account {name: $name, status: 'UNVERIFIED', event_id: $event_id, source: $source})",
                "parameters": {
                    "name": company_name, 
                    "event_id": event_id,
                    "source": source
                }
            })
            query_resp.raise_for_status()
            
            write_latency_ms = (time.monotonic() - start_time) * 1000
            logger.info(f"BRANCH_CREATED branch={branch_id} entity='{company_name}' latency_ms={write_latency_ms:.1f}")
            
            return branch_id
            
        except Exception as e:
            logger.error(f"Failed to ingest entity '{company_name}' into branch {branch_id}: {e}")
            return None

    def evaluate_and_merge(self, branch_id: str, evidence_score: int, threshold: int = 70) -> bool:
        """
        The Merge Threshold: Evaluates evidence. 
        If evidence_score > threshold, fast-forward merge into main graph.
        Else, drop the branch to prevent graph pollution.
        """
        start_time = time.monotonic()
        logger.info(f"Evaluating merge for branch '{branch_id}' (score: {evidence_score})")
        
        try:
            if evidence_score > threshold:
                # 1. Promote entity to VERIFIED status on the branch
                requests.post(f"{self.server_url}/query", json={
                    "branch": branch_id,
                    "query": "MATCH (a:Account) SET a.status = 'VERIFIED'"
                }).raise_for_status()
                
                # 2. Fast-forward merge into main branch
                merge_resp = requests.post(f"{self.server_url}/branches/{branch_id}/merge", json={
                    "target": self.main_branch,
                    "strategy": "fast-forward"
                })
                merge_resp.raise_for_status()
                
                merge_latency_ms = (time.monotonic() - start_time) * 1000
                logger.info(f"MERGE_SUCCESS branch={branch_id} score={evidence_score} latency_ms={merge_latency_ms:.1f}")
                return True
                
            else:
                # Drop the branch to prevent pollution
                requests.delete(f"{self.server_url}/branches/{branch_id}").raise_for_status()
                logger.warning(f"MERGE_DROPPED branch={branch_id} score={evidence_score} < threshold={threshold}. Branch deleted.")
                return False
                
        except Exception as e:
            logger.error(f"Error during merge evaluation for branch {branch_id}: {e}")
            return False

if __name__ == "__main__":
    # Test simulation
    sink = OmnigraphSink()
    
    # 1. Simulate incoming unverified entity
    test_evt = AccountEvent(
        source="SEC_EDGAR",
        company_name="Ghost Corp Inc",
        raw_text="Potential material agreement found."
    )
    
    branch = sink.ingest_unverified_entity(test_evt)
    
    if branch:
        # 2. Simulate evidence corroboration
        sink.evaluate_and_merge(branch, evidence_score=85)
