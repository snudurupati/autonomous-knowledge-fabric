# tests/test_tier3.py
# Unit tests for the Tier-3 LLM-as-Judge entity resolver with Rehydration Cache.

import os
import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.resolver.tier3_llm_judge import LLMJudgeResolver, Tier3Match

@pytest.fixture
def mock_client():
    return MagicMock()

@pytest.fixture(autouse=True)
def setup_test_cache(tmp_path):
    """Set up a temporary cache database for each test."""
    test_db = tmp_path / "test_resolver_cache.db"
    with patch.dict(os.environ, {"AKF_RESOLVER_CACHE": str(test_db)}):
        yield test_db
    if test_db.exists():
        os.remove(test_db)

@patch("google.genai.Client")
def test_resolve_llm_match(mock_genai_client_class, mock_client):
    # Mock Gemini response
    mock_genai_client = mock_genai_client_class.return_value
    mock_response = MagicMock()
    mock_response.parsed = Tier3Match(
        node_key="existing_key", 
        confidence=0.95, 
        reasoning="Names are highly similar."
    )
    mock_genai_client.models.generate_content.return_value = mock_response

    resolver = LLMJudgeResolver(mock_client, api_key="fake-key")
    
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme Corp",
        company_domain="acme.com",
        raw_text="test"
    )
    
    mock_client.find_potential_matches.return_value = []
    mock_client.find_by_name.return_value = [
        {"node_key": "existing_key", "company_name": "Acme Inc.", "domain": "acme.com", "cik_number": None, "signals": []}
    ]
    
    result = resolver.resolve(event)
    assert result is not None
    assert result["node_key"] == "existing_key"
    assert result["confidence"] == 0.95
    assert result["tier"] == 3
    assert "Names are highly similar" in result["reasoning"]

@patch("google.genai.Client")
def test_resolve_caching_logic(mock_genai_client_class, mock_client):
    """Verify that a second call for the same entity pair hits the cache."""
    mock_genai_client = mock_genai_client_class.return_value
    mock_response = MagicMock()
    mock_response.parsed = Tier3Match(
        node_key="cache_key", 
        confidence=0.99, 
        reasoning="Identical company."
    )
    mock_genai_client.models.generate_content.return_value = mock_response

    resolver = LLMJudgeResolver(mock_client, api_key="fake-key")
    
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Cache Corp",
        company_domain="cache.com",
        raw_text="test"
    )
    
    mock_client.find_potential_matches.return_value = []
    mock_client.find_by_name.return_value = [
        {"node_key": "cache_key", "company_name": "Cache Inc.", "domain": "cache.com", "cik_number": None, "signals": []}
    ]
    
    # First call: hits LLM
    result1 = resolver.resolve(event)
    assert result1["node_key"] == "cache_key"
    assert mock_genai_client.models.generate_content.call_count == 1
    
    # Second call: hits cache
    result2 = resolver.resolve(event)
    assert result2["node_key"] == "cache_key"
    assert "(CACHED)" in result2["reasoning"]
    # LLM should NOT have been called again
    assert mock_genai_client.models.generate_content.call_count == 1

@patch("google.genai.Client")
def test_resolve_llm_no_match(mock_genai_client_class, mock_client):
    mock_genai_client = mock_genai_client_class.return_value
    mock_response = MagicMock()
    mock_response.parsed = Tier3Match(
        node_key=None, 
        confidence=0.2, 
        reasoning="Totally different companies."
    )
    mock_genai_client.models.generate_content.return_value = mock_response

    resolver = LLMJudgeResolver(mock_client, api_key="fake-key")
    
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme Corp",
        cik_number="123",
        raw_text="test"
    )
    
    mock_client.find_potential_matches.return_value = []
    mock_client.find_by_name.return_value = [
        {"node_key": "other_key", "company_name": "Other Corp", "domain": "other.com", "cik_number": None, "signals": []}
    ]
    
    result = resolver.resolve(event)
    assert result is None

def test_resolve_no_api_key(mock_client):
    with patch.dict(os.environ, {"GOOGLE_API_KEY": ""}, clear=False):
        res = LLMJudgeResolver(mock_client, api_key=None)
        event = AccountEvent(
            source=EventSource.SEC_EDGAR, 
            company_name="Test", 
            company_domain="test.com",
            raw_text="test"
        )
        assert res.resolve(event) is None
