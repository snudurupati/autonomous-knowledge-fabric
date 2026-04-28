# pipelines/routing.py
# Shared logic for event buffering and promotion using Omnigraph side-branches.

import logging
from typing import Optional, Any
from models.account_event import AccountEvent
from engine.omnigraph.ingestion_sink import OmnigraphSink

logger = logging.getLogger(__name__)

class OmnigraphRoutingManager:
    """
    Manages entity resolution routing using Omnigraph side-branches.
    Replaces the legacy in-memory GhostNodeManager.
    """
    def __init__(self, sink: Optional[OmnigraphSink] = None):
        self.sink = sink or OmnigraphSink()

    def process_event(self, event: AccountEvent) -> bool:
        """
        Process an event. 
        Creates a side-branch in Omnigraph.
        If it's a "Strong Signal" (has identifiers), merges immediately.
        Otherwise, leaves it in the side-branch for future resolution.
        
        Returns True if promoted (merged to main), False if branched.
        """
        # 1. Branch-Based Buffering: Every entity fragment starts in its own branch
        # This replaces the in-memory self.buffer from GhostNodeManager
        branch_id = self.sink.ingest_unverified_entity(event)
        
        if not branch_id:
            logger.error(f"Routing failed: Could not create branch for {event.company_name}")
            return False

        # 2. Strong Signal Check (Immediate Promotion)
        # If we have identifiers, we have high confidence (Score 100)
        has_strong_signal = bool(event.cik_number or event.company_domain or event.account_id)
        
        if has_strong_signal:
            return self.sink.evaluate_and_merge(branch_id, evidence_score=100)
        else:
            # For "Weak Signals" (name only), we keep the branch open.
            # In Sprint 17+, a separate corroboration service or Tier-3 LLM 
            # will call evaluate_and_merge later.
            logger.info(f"Event branched: {event.company_name} is now buffered in Omnigraph branch '{branch_id}'")
            return False

_manager: Optional[OmnigraphRoutingManager] = None

def get_routing_manager() -> OmnigraphRoutingManager:
    """Singleton getter for the routing manager."""
    global _manager
    if _manager is None:
        _manager = OmnigraphRoutingManager()
    return _manager
