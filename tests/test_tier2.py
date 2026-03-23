# tests/test_tier2.py
# Unit tests for the Tier-2 graph-contextual entity resolver.

import pytest
from unittest.mock import MagicMock
from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.resolver.tier2_graph_context import GraphContextResolver

@pytest.fixture
def mock_client():
    return MagicMock()

@pytest.fixture
def resolver(mock_client):
    return GraphContextResolver(mock_client)

def test_resolve_by_domain(resolver, mock_client):
    # Event with a domain that matches an existing node
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme Corp",
        company_domain="acme.com",
        raw_text="test"
    )
    mock_client.find_potential_matches.return_value = [
        {"node_key": "existing_key", "company_name": "Acme", "domain": "acme.com", "cik_number": None, "signals": []}
    ]
    mock_client.find_by_name.return_value = []
    
    result = resolver.resolve(event)
    assert result is not None
    assert result["node_key"] == "existing_key"
    assert result["confidence"] == 0.85

def test_resolve_by_cik(resolver, mock_client):
    # Event with a CIK that matches an existing node
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme Corp",
        cik_number="12345",
        raw_text="test"
    )
    mock_client.find_potential_matches.return_value = [
        {"node_key": "existing_key", "company_name": "Acme", "domain": None, "cik_number": "12345", "signals": []}
    ]
    mock_client.find_by_name.return_value = []
    
    result = resolver.resolve(event)
    assert result is not None
    assert result["node_key"] == "existing_key"
    assert result["confidence"] == 1.0

def test_no_match_below_threshold(resolver, mock_client):
    # Event with similar name and only ONE shared signal (confidence 0.3 + 0.4 = 0.7 < 0.75)
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme subsidiary",
        company_domain="acme-sub.com",
        risk_signals=[RiskSignal.TAKEOVER_BID],
        raw_text="test"
    )
    mock_client.find_potential_matches.return_value = []
    mock_client.find_by_name.return_value = [
        {"node_key": "parent_key", "company_name": "Acme Corp", "domain": "acme.com", "cik_number": None, "signals": ["TAKEOVER_BID"]}
    ]
    
    result = resolver.resolve(event)
    assert result is None

def test_resolve_by_multiple_shared_signals(resolver, mock_client):
    # Event with similar name and TWO shared signals (confidence 0.3 + 0.65 = 0.95 >= 0.75)
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme subsidiary",
        company_domain="acme-sub.com",
        risk_signals=[RiskSignal.TAKEOVER_BID, RiskSignal.EARNINGS_MISS],
        raw_text="test"
    )
    mock_client.find_potential_matches.return_value = []
    mock_client.find_by_name.return_value = [
        {"node_key": "parent_key", "company_name": "Acme Corp", "domain": "acme.com", "cik_number": None, "signals": ["TAKEOVER_BID", "EARNINGS_MISS"]}
    ]
    
    result = resolver.resolve(event)
    assert result is not None
    assert result["node_key"] == "parent_key"
    assert result["confidence"] == 0.95

def test_resolve_prefers_strongest_match(resolver, mock_client):
    # Event matches one node by domain (0.85) and another by CIK (1.0)
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Mixed Corp",
        company_domain="match-domain.com",
        cik_number="match-cik",
        raw_text="test"
    )
    mock_client.find_potential_matches.return_value = [
        {"node_key": "key_domain", "company_name": "Domain Corp", "domain": "match-domain.com", "cik_number": "other", "signals": []},
        {"node_key": "key_cik", "company_name": "CIK Corp", "domain": "other.com", "cik_number": "match-cik", "signals": []}
    ]
    mock_client.find_by_name.return_value = []
    
    result = resolver.resolve(event)
    assert result["node_key"] == "key_cik"
    assert result["confidence"] == 1.0
