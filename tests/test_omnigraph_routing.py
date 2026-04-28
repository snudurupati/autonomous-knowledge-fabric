# tests/test_omnigraph_routing.py
# Unit tests for the Omnigraph Routing logic (Branch-based buffering).

import pytest
from unittest.mock import MagicMock, patch
from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.routing import OmnigraphRoutingManager

@pytest.fixture
def mock_sink():
    sink = MagicMock()
    # Mock ingest_unverified_entity to return a branch ID
    sink.ingest_unverified_entity.return_value = "fragment/abc12345"
    # Mock evaluate_and_merge to return True if score is high
    sink.evaluate_and_merge.side_effect = lambda branch_id, evidence_score: evidence_score >= 70
    return sink

@pytest.fixture
def manager(mock_sink):
    return OmnigraphRoutingManager(sink=mock_sink)

def test_promotion_by_strong_signal_cik(manager, mock_sink):
    # Event with CIK should promote immediately via merge
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Strong Corp",
        cik_number="12345",
        raw_text="test"
    )
    promoted = manager.process_event(event)
    
    assert promoted is True
    assert mock_sink.ingest_unverified_entity.call_count == 1
    assert mock_sink.evaluate_and_merge.call_count == 1
    # Strong signal should use score 100
    mock_sink.evaluate_and_merge.assert_called_with("fragment/abc12345", evidence_score=100)

def test_promotion_by_strong_signal_domain(manager, mock_sink):
    # Event with domain should promote immediately
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Domain Corp",
        company_domain="domain.com",
        raw_text="test"
    )
    promoted = manager.process_event(event)
    
    assert promoted is True
    assert mock_sink.evaluate_and_merge.call_count == 1

def test_branching_of_weak_signal(manager, mock_sink):
    # Event with ONLY name should be branched but NOT merged
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
    assert mock_sink.ingest_unverified_entity.call_count == 1
    assert mock_sink.evaluate_and_merge.call_count == 0

def test_failed_branch_creation(manager, mock_sink):
    # If branch creation fails, routing should return False
    mock_sink.ingest_unverified_entity.return_value = None
    
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Fail Corp",
        cik_number="123", # Strong signal but branch creation fails
        raw_text="test"
    )
    promoted = manager.process_event(event)
    
    assert promoted is False
    assert mock_sink.evaluate_and_merge.call_count == 0
