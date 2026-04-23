# pipelines/routing.py
# Shared logic for event buffering and promotion (Ghost Node Pattern).

import time
import warnings
from typing import Dict, List, Optional, Any
from models.account_event import AccountEvent
from graph.memgraph_client import MemgraphClient
from pipelines.resolver.tier1_deterministic import normalize
from observability.telemetry import latency_tracker

class GhostNodeManager:
    """
    Manages stateful buffering of AccountEvents.
    Promotes to real nodes based on Strong Signal or Corroboration.
    """
    def __init__(self, client: Optional[MemgraphClient] = None, window_secs: int = 3600):
        self.client = client or MemgraphClient()
        self.window_secs = window_secs
        # Buffer schema: {normalized_name: [AccountEvent, ...]}
        self.buffer: Dict[str, List[AccountEvent]] = {}
        # Timestamps of first event in buffer: {normalized_name: first_event_ts}
        self.first_event_ts: Dict[str, float] = {}

    def process_event(self, event: AccountEvent) -> bool:
        """
        Process an event. Returns True if promoted/written to graph, False if buffered.
        """
        # 1. Strong Signal Check (Immediate Promotion)
        if event.cik_number or event.company_domain or event.account_id:
            self._flush_group(event.company_name, [event])
            return True

        # 2. Corroboration Check (Stateful Buffer)
        norm_name = normalize(event.company_name)
        now = time.monotonic()

        # Global cleanup check every 100 events to prevent leak from one-off events
        processed_count = getattr(self, "_processed_count", 0)
        if processed_count % 100 == 0:
            stale_names = [n for n, ts in self.first_event_ts.items() if now - ts > self.window_secs]
            for n in stale_names:
                del self.buffer[n]
                del self.first_event_ts[n]
        self._processed_count = processed_count + 1

        # Per-name cleanup on access
        if norm_name in self.first_event_ts:
            if now - self.first_event_ts[norm_name] > self.window_secs:
                del self.buffer[norm_name]
                del self.first_event_ts[norm_name]

        if norm_name not in self.buffer:
            self.buffer[norm_name] = [event]
            self.first_event_ts[norm_name] = now
            return False
        else:
            self.buffer[norm_name].append(event)
            # Threshold: 2+ distinct events (we use len(buffer) as proxy for corroboration)
            if len(self.buffer[norm_name]) >= 2:
                events_to_flush = self.buffer.pop(norm_name)
                del self.first_event_ts[norm_name]
                self._flush_group(event.company_name, events_to_flush)
                return True
            return False

    def _flush_group(self, company_name: str, events: List[AccountEvent]):
        """Write a group of events to the graph through the resolver stack."""
        for event in events:
            try:
                # record received for tracking if not already done by source
                # (but here we assume it's a centralized sink)
                self.client.upsert_event(event)
                latency_tracker.record_graph_written(event.event_id)
            except Exception as exc:
                warnings.warn(f"GhostNodeManager: Graph write failed for {company_name}: {exc}")

_manager: Optional[GhostNodeManager] = None

def get_ghost_manager() -> GhostNodeManager:
    global _manager
    if _manager is None:
        _manager = GhostNodeManager()
    return _manager
