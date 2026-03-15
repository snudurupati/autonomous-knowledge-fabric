# tests/test_context_api.py
# Integration tests for the context API layer — requires live Memgraph on localhost:7687.

import pytest

from graph.memgraph_client import MemgraphClient
from graph.context_api import get_agent_context, freshness_label
from models.account_event import AccountEvent, EventSource, RiskSignal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> MemgraphClient:
    c = MemgraphClient()
    yield c
    c.close()


@pytest.fixture(autouse=True)
def clean_test_accounts(client: MemgraphClient) -> None:
    client._run("MATCH (a:Account) WHERE a.company_name STARTS WITH 'test_ctx_' DETACH DELETE a")


def _make_event(
    company: str = "test_ctx_acme",
    signals: list[RiskSignal] | None = None,
) -> AccountEvent:
    return AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name=company,
        company_domain=f"{company.replace('test_ctx_', '')}.com",
        account_id=f"SF-CTX-{company}",
        raw_text=f"Annual report filing for {company}",
        risk_signals=signals or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_account_context_structure(client: MemgraphClient) -> None:
    """Upsert a test account and verify all 7 keys + types."""
    event = _make_event(
        "test_ctx_acme",
        signals=[RiskSignal.EARNINGS_MISS, RiskSignal.EXECUTIVE_DEPARTURE],
    )
    client.upsert_event(event)

    ctx = client.get_account_context("test_ctx_acme")
    assert ctx is not None

    expected_keys = {
        "company_name", "cik_number", "last_updated",
        "total_events", "recent_events", "risk_signals", "context_age_seconds",
    }
    assert expected_keys == set(ctx.keys())

    assert isinstance(ctx["company_name"], str)
    assert isinstance(ctx["total_events"], int)
    assert isinstance(ctx["recent_events"], list)
    assert isinstance(ctx["risk_signals"], list)
    assert isinstance(ctx["context_age_seconds"], int)
    assert ctx["context_age_seconds"] >= 0
    assert "EARNINGS_MISS" in ctx["risk_signals"]
    assert "EXECUTIVE_DEPARTURE" in ctx["risk_signals"]


def test_get_high_risk_accounts_returns_list(client: MemgraphClient) -> None:
    """get_high_risk_accounts returns a list of dicts with expected keys."""
    results = client.get_high_risk_accounts()
    assert isinstance(results, list)
    for item in results:
        assert "company" in item
        assert "signals" in item
        assert "signal_count" in item
        assert isinstance(item["signals"], list)
        assert isinstance(item["signal_count"], int)


def test_get_agent_context_carbonite() -> None:
    """get_agent_context for 'carbonite' returns a properly formatted report."""
    report = get_agent_context("carbonite")
    assert isinstance(report, str)
    assert len(report) > 0
    # Either we get a real report or a "no data" message — both are valid
    assert "ACCOUNT INTELLIGENCE REPORT" in report or "No data found" in report
    # If we got a real report, check structure
    if "ACCOUNT INTELLIGENCE REPORT" in report:
        assert "Context Freshness" in report


def test_context_freshness_label() -> None:
    """freshness_label returns correct LIVE / RECENT / STALE strings."""
    assert freshness_label(5) == "LIVE (sub-60s)"
    assert freshness_label(0) == "LIVE (sub-60s)"
    assert freshness_label(59) == "LIVE (sub-60s)"
    assert freshness_label(60) == "RECENT (60-300s)"
    assert freshness_label(120) == "RECENT (60-300s)"
    assert freshness_label(299) == "RECENT (60-300s)"
    assert freshness_label(300) == "STALE (300s)"
    assert freshness_label(400) == "STALE (400s)"
