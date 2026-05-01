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
        If it's a "Strong Signal" (has identifiers), promotes immediately via FAST-PATH.
        Otherwise, creates a side-branch in Omnigraph for future resolution.
        
        Returns True if promoted (merged or direct to main), False if branched.
        """
        # 1. Strong Signal Check (Immediate Promotion / Fast-Path)
        # If we have identifiers, we bypass side-branches to avoid merge conflicts
        # and non-graceful server errors.
        has_strong_signal = bool(event.cik_number or event.company_domain or event.account_id)
        
        if has_strong_signal:
            logger.info(f"Fast-Path: Ingesting high-confidence event for {event.company_name} directly to main")
            # Temporarily disable buffering for this specific call to hit 'main'
            original_buffering = self.sink.use_buffering
            self.sink.use_buffering = False
            try:
                self.sink.ingest_event(event)
                return True
            except Exception as e:
                logger.error(f"Fast-Path ingestion failed for {event.company_name}: {e}")
                return False
            finally:
                self.sink.use_buffering = original_buffering

        # 2. Branch-Based Buffering: Weak signals start in their own branch
        # This replaces the in-memory self.buffer from GhostNodeManager
        branch_id = self.sink.ingest_unverified_entity(event)
        
        if not branch_id:
            logger.error(f"Routing failed: Could not create branch for {event.company_name}")
            return False

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
