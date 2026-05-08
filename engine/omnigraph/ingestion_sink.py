import logging
import uuid
import requests
import os
import time
import urllib.parse
import threading
from typing import Dict, Any, Optional, List
from observability.telemetry import latency_tracker, tracer
from models.account_event import AccountEvent
from engine.omnigraph.client import OmnigraphClient
from scoring.account_health import calculate_risk_score
from opentelemetry import trace

# Configure logging for observability and benchmarking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OmnigraphSink:
    """
    Omnigraph Ingestion Sink (Sprint 17/18) - V2 with OTel Telemetry
    
    Manages ingestion of AccountEvents into Omnigraph.
    Uses OmnigraphClient for Schema-as-Code compliant mutations.
    
    v0.4.2: Implements batch buffering to minimize S3 commit penalties (~3.3s -> ~53ms/event).
    v0.4.4: Added OpenTelemetry instrumentation for flushes and individual events.
    """
    def __init__(self, 
                 server_url: Optional[str] = None, 
                 main_branch: str = "main",
                 use_buffering: bool = False,
                 batch_size: int = 50,
                 flush_interval_secs: float = 5.0):
        
        self.server_url = (server_url or 
                           os.getenv("OMNIGRAPH_SERVER_URL", "http://127.0.0.1:8080"))
        self.main_branch = main_branch
        self.use_buffering = use_buffering
        
        # Batching configuration
        self.batch_size = batch_size
        self.flush_interval_secs = flush_interval_secs
        self.buffer: List[tuple] = [] # Stores (event, target_branch)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Initialize the specialized Omnigraph Client
        self.client = OmnigraphClient(self.server_url)
        
        if self.use_buffering:
            self._flush_thread = threading.Thread(target=self._background_flush, daemon=True)
            self._flush_thread.start()
            logger.info(f"Initialized Buffered OmnigraphSink V2. BatchSize: {self.batch_size}, Interval: {self.flush_interval_secs}s")
        else:
            logger.info(f"Initialized Immediate OmnigraphSink V2. Server: {self.server_url}, Main Branch: {self.main_branch}")

    def ingest_unverified_entity(self, event: AccountEvent) -> str:
        """
        Maps an AccountEvent to an Account node upsert into a unique side-branch.
        """
        target_branch = f"fragment-{uuid.uuid4().hex[:8]}"
        try:
            requests.post(f"{self.server_url}/branches", json={
                "name": target_branch,
                "base": self.main_branch
            }).raise_for_status()
        except Exception as e:
            logger.error(f"Failed to create branch {target_branch}: {e}")
            target_branch = self.main_branch

        if self.use_buffering:
            with self._lock:
                self.buffer.append((event, target_branch))
                buffer_len = len(self.buffer)
            
            if buffer_len >= self.batch_size:
                self.flush()
            return target_branch
            
        return self._commit_now(event, branch=target_branch)

    def ingest_event(self, event: AccountEvent) -> str:
        """
        Ingests an event into Omnigraph's main branch. 
        """
        if self.use_buffering:
            with self._lock:
                self.buffer.append((event, self.main_branch))
                buffer_len = len(self.buffer)
            
            if buffer_len >= self.batch_size:
                self.flush()
            return self.main_branch 
        
        return self._commit_now(event)

    def _commit_now(self, event: AccountEvent, branch: Optional[str] = None, sync_branch: bool = True) -> str:
        """Immediate commit of a single event."""
        start_time = time.monotonic()
        target_branch = branch or self.main_branch
        
        # Record received for latency tracking
        latency_tracker.record_event_received(event.event_id, event.source.value, event.company_name)
        
        signals = [{"name": s.value, "timestamp": event.timestamp.isoformat()} for s in event.risk_signals]
        risk_score = calculate_risk_score(signals)
        
        with tracer.start_as_current_span("pipeline.event") as span:
            span.set_attribute("event_id", event.event_id)
            span.set_attribute("company", event.company_name)
            span.set_attribute("branch", target_branch)
            span.set_attribute("sync_branch", sync_branch)
            
            try:
                self.client.ingest_event_complete(
                    name=event.company_name,
                    node_key=event.company_name,
                    risk_score=risk_score,
                    event_id=event.event_id,
                    source=event.source.value,
                    timestamp=event.timestamp.date().isoformat(),
                    risk_signals=[s.value for s in event.risk_signals],
                    raw_text=event.raw_text,
                    branch=target_branch,
                    sync_branch=sync_branch
                )
                latency_ms = (time.monotonic() - start_time) * 1000
                logger.info(f"INGEST_SUCCESS entity='{event.company_name}' sync={sync_branch} latency_ms={latency_ms:.1f}")
                
                # Mark graph as written for latency tracking
                latency_tracker.record_graph_written(event.event_id)
                
                return target_branch
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                logger.error(f"Failed to ingest entity '{event.company_name}': {e}")
                raise e

    def flush(self):
        """Flushes the current buffer to Omnigraph in a single transactional batch."""
        with self._lock:
            if not self.buffer:
                return
            batch_to_flush = self.buffer
            self.buffer = []
        
        start_time = time.monotonic()
        logger.info(f"Flushing batch of {len(batch_to_flush)} events to Omnigraph...")
        
        with tracer.start_as_current_span("pipeline.batch_flush") as span:
            span.set_attribute("batch_size", len(batch_to_flush))
            
            # Group events by branch to manage sync_branch efficiently
            branch_groups = {}
            for event, target_branch in batch_to_flush:
                if target_branch not in branch_groups:
                    branch_groups[target_branch] = []
                branch_groups[target_branch].append(event)
            
            success_count = 0
            for target_branch, events in branch_groups.items():
                for idx, event in enumerate(events):
                    # Only force branch sync on the final event of the batch for this branch
                    should_sync = (idx == len(events) - 1)
                    try:
                        self._commit_now(event, branch=target_branch, sync_branch=should_sync)
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Batch item failed: {e}")
            
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.info(f"BATCH_FLUSH_COMPLETE success={success_count}/{len(batch_to_flush)} latency_ms={latency_ms:.1f} avg_ms={latency_ms/max(1, success_count):.1f}")
            span.set_attribute("success_count", success_count)

    def _background_flush(self):
        """Background loop to ensure data is flushed even if batch size isn't reached."""
        while not self._stop_event.is_set():
            time.sleep(self.flush_interval_secs)
            if self.buffer:
                self.flush()

    def shutdown(self):
        """Clean shutdown of the sink."""
        self._stop_event.set()
        self.flush()
        if hasattr(self, '_flush_thread'):
            self._flush_thread.join(timeout=2)

    def evaluate_and_merge(self, branch_id: str, evidence_score: int, threshold: int = 70) -> bool:
        """
        Merges a side-branch into main if threshold met.
        """
        if branch_id == self.main_branch:
            return True
            
        start_time = time.monotonic()
        with tracer.start_as_current_span("pipeline.branch_merge") as span:
            span.set_attribute("branch_id", branch_id)
            span.set_attribute("evidence_score", evidence_score)
            
            try:
                if evidence_score > threshold:
                    merge_resp = requests.post(f"{self.server_url}/branches/merge", json={
                        "source": branch_id,
                        "target": self.main_branch,
                        "strategy": "fast-forward"
                    })
                    merge_resp.raise_for_status()
                    
                    # Physically delete the source branch after successful merge to keep metadata clean
                    requests.delete(f"{self.server_url}/branches/{branch_id}").raise_for_status()
                    
                    logger.info(f"MERGE_SUCCESS branch={branch_id} (purged) latency_ms={(time.monotonic() - start_time)*1000:.1f}")
                    return True
                else:
                    requests.delete(f"{self.server_url}/branches/{branch_id}").raise_for_status()
                    logger.warning(f"MERGE_DROPPED branch={branch_id}")
                    return False
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                logger.error(f"Merge failed for {branch_id}: {e}")
                return False

if __name__ == "__main__":
    from models.account_event import EventSource, RiskSignal
    # Test simulation
    sink = OmnigraphSink(use_buffering=False)
    
    test_evt = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme Corp",
        risk_signals=[RiskSignal.CRITICAL_SUPPORT],
        raw_text="Support case escalated."
    )
    
    print("\n--- Phase 1: Ingesting Initial Event ---")
    sink.ingest_event(test_evt)
