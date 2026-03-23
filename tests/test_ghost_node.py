# tests/test_ghost_node.py
# Unit tests for the Ghost Node Pattern promotion logic.

import pytest
from unittest.mock import MagicMock, patch
from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.routing import GhostNodeManager

@pytest.fixture
def mock_client():
    return MagicMock()

@pytest.fixture
def manager(mock_client):
    return GhostNodeManager(client=mock_client)

def test_promotion_by_strong_signal_cik(manager, mock_client):
    # Event with CIK should promote immediately
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Strong Corp",
        cik_number="12345",
        raw_text="test"
    )
    promoted = manager.process_event(event)
    assert promoted is True
    assert mock_client.upsert_event.call_count == 1

def test_promotion_by_strong_signal_domain(manager, mock_client):
    # Event with domain should promote immediately
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Domain Corp",
        company_domain="domain.com",
        raw_text="test"
    )
    promoted = manager.process_event(event)
    assert promoted is True
    assert mock_client.upsert_event.call_count == 1

def test_buffering_of_weak_signal(manager, mock_client):
    # Event with ONLY name should be buffered (Ghost Node)
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Weak Corp",
        raw_text="test",
        # No identifiers
        company_domain=None,
        cik_number=None,
        account_id=None
    )
    promoted = manager.process_event(event)
    assert promoted is False
    assert mock_client.upsert_event.call_count == 0
    # "Corp" is stripped by normalize() -> "weak"
    assert "weak" in manager.buffer

def test_promotion_by_corroboration(manager, mock_client):
    # Two weak events for the same company should trigger promotion
    event1 = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Corroborate Inc",
        raw_text="event 1"
    )
    event2 = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Corroborate Inc",
        raw_text="event 2"
    )
    
    # First event: buffers
    assert manager.process_event(event1) is False
    assert mock_client.upsert_event.call_count == 0
    
    # Second event: promotes both
    assert manager.process_event(event2) is True
    # _flush_group is called with [event1, event2]
    assert mock_client.upsert_event.call_count == 2

def test_stale_buffer_cleanup(manager, mock_client):
    # Test that stale buffer entries are cleaned up
    manager.window_secs = 0 # Immediate stale
    event1 = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Stale Corp",
        raw_text="event 1"
    )
    
    manager.process_event(event1)
    # "Corp" stripped -> "stale"
    assert "stale" in manager.buffer
    
    # Wait or simulate time passage
    import time
    with patch("time.monotonic", return_value=time.monotonic() + 10):
        event2 = AccountEvent(
            source=EventSource.SEC_EDGAR,
            company_name="Stale Corp",
            raw_text="event 2"
        )
        # It will see event1 is stale, delete it, then add event2 as the NEW first event
        assert manager.process_event(event2) is False
        assert len(manager.buffer["stale"]) == 1
        assert manager.buffer["stale"][0] == event2
