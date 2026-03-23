# tests/test_memgraph_client.py
# Integration tests for MemgraphClient — requires Memgraph running on localhost:7687.

import pytest
from unittest.mock import patch, MagicMock

from graph.memgraph_client import MemgraphClient
from models.account_event import AccountEvent, EventSource, RiskSignal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> MemgraphClient:
    """Single client shared across all tests in this module."""
    c = MemgraphClient()
    yield c
    c.close()


@pytest.fixture(autouse=True)
def clean_test_accounts(client: MemgraphClient) -> None:
    """Remove test nodes before each test to ensure isolation."""
    client._run("MATCH (a:Account) WHERE a.company_name STARTS WITH 'test_' DETACH DELETE a")
    client._run("MATCH (e:Event) WHERE e.source = 'SALESFORCE' DETACH DELETE e")
    client._run("MATCH (alias:Alias) WHERE alias.company_name STARTS WITH 'test_' DETACH DELETE alias")


def _make_event(
    company: str = "test_acme",
    signals: list[RiskSignal] | None = None,
    source: EventSource = EventSource.SALESFORCE,
) -> AccountEvent:
    return AccountEvent(
        source=source,
        company_name=company,
        company_domain=f"{company.replace('test_', '')}.com",
        account_id=f"SF-TEST-{company}",
        raw_text="test raw text",
        risk_signals=signals or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_upsert_account_creates_node(client: MemgraphClient) -> None:
    event = _make_event("test_acme")
    client.upsert_account(event)

    rows = client._run(
        "MATCH (a:Account {company_name: $n}) RETURN a",
        {"n": "test_acme"},
    )
    assert len(rows) == 1
    node = dict(rows[0]["a"])
    assert node["company_name"] == "test_acme"
    assert node["domain"] == "acme.com"
    assert node["source"] == "SALESFORCE"


def test_upsert_account_no_duplicates_on_repeat(client: MemgraphClient) -> None:
    event = _make_event("test_acme")
    client.upsert_account(event)
    client.upsert_account(event)  # second upsert — MERGE must not create a duplicate

    rows = client._run(
        "MATCH (a:Account {company_name: $n}) RETURN count(a) AS cnt",
        {"n": "test_acme"},
    )
    assert rows[0]["cnt"] == 1


def test_upsert_account_creates_risk_signal_nodes(client: MemgraphClient) -> None:
    event = _make_event(
        "test_bigcorp",
        signals=[RiskSignal.CONTRACT_RENEWAL_AT_RISK, RiskSignal.CRITICAL_SUPPORT],
    )
    client.upsert_account(event)

    rows = client._run(
        """
        MATCH (a:Account {company_name: $n})-[:HAS_SIGNAL]->(s:RiskSignal)
        RETURN s.name AS signal
        """,
        {"n": "test_bigcorp"},
    )
    signal_names = {r["signal"] for r in rows}
    assert "CONTRACT_RENEWAL_AT_RISK" in signal_names
    assert "CRITICAL_SUPPORT" in signal_names


def test_upsert_account_no_duplicate_signal_edges(client: MemgraphClient) -> None:
    event = _make_event("test_bigcorp", signals=[RiskSignal.TAKEOVER_BID])
    client.upsert_account(event)
    client.upsert_account(event)  # second upsert

    rows = client._run(
        """
        MATCH (a:Account {company_name: $n})-[r:HAS_SIGNAL]->(:RiskSignal {name: 'TAKEOVER_BID'})
        RETURN count(r) AS cnt
        """,
        {"n": "test_bigcorp"},
    )
    assert rows[0]["cnt"] == 1


def test_upsert_event_creates_event_node_and_filed_edge(client: MemgraphClient) -> None:
    event = _make_event("test_acme")
    client.upsert_event(event)

    rows = client._run(
        """
        MATCH (a:Account {company_name: $n})-[:FILED]->(e:Event {event_id: $eid})
        RETURN e.source AS source
        """,
        {"n": "test_acme", "eid": event.event_id},
    )
    assert len(rows) == 1
    assert rows[0]["source"] == "SALESFORCE"


def test_get_account_with_relationships_returns_correct_structure(
    client: MemgraphClient,
) -> None:
    event = _make_event("test_acme", signals=[RiskSignal.EXECUTIVE_DEPARTURE])
    client.upsert_event(event)

    result = client.get_account_with_relationships("test_acme")
    assert result is not None
    assert result["account"]["company_name"] == "test_acme"

    rel_types = {r["type"] for r in result["relationships"]}
    assert "HAS_SIGNAL" in rel_types
    assert "FILED" in rel_types


def test_get_account_returns_none_for_missing(client: MemgraphClient) -> None:
    result = client.get_account_with_relationships("test_nonexistent_xyz")
    assert result is None


def test_upsert_account_tier2_merge_by_domain(client: MemgraphClient) -> None:
    from pipelines.resolver.tier1_deterministic import resolve as tier1_resolve

    # 1. Create original node
    event1 = _make_event("test_original", source=EventSource.SALESFORCE)
    event1.company_domain = "unique-domain.com"
    client.upsert_account(event1)

    # 2. Upsert different name with same domain
    event2 = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="test_alias_name",
        company_domain="unique-domain.com",
        cik_number="99999",  # New info
        raw_text="some 8-k",
    )
    node_key = client.upsert_account(event2)

    # 3. Verify it used the same node_key as the original
    orig_node_key = tier1_resolve("test_original")["hash"]
    assert node_key == orig_node_key

    # 4. Verify Alias node and MERGED_FROM edge
    alias_key = tier1_resolve("test_alias_name")["hash"]
    rows = client._run(
        "MATCH (alias:Alias {node_key: $ak})-[:MERGED_FROM]->(target:Account) RETURN target.node_key AS tk",
        {"ak": alias_key},
    )
    assert len(rows) == 1
    assert rows[0]["tk"] == orig_node_key

    # 5. Verify target node was updated with new info (CIK)
    rows = client._run(
        "MATCH (a:Account {node_key: $k}) RETURN a.cik_number AS cik",
        {"k": orig_node_key},
    )
    assert rows[0]["cik"] == "99999"


@patch("pipelines.resolver.tier3_llm_judge.LLMJudgeResolver.resolve")
def test_upsert_account_tier3_merge(mock_resolve: MagicMock, client: MemgraphClient) -> None:
    from pipelines.resolver.tier1_deterministic import resolve as tier1_resolve

    # Initialize mock to return None (no Tier 3 match by default)
    mock_resolve.return_value = None

    # 1. Create original node
    event1 = _make_event("test_target_t3", source=EventSource.SALESFORCE)
    event1.company_domain = "target-t3.com"
    client.upsert_account(event1)
    target_key = tier1_resolve("test_target_t3")["hash"]

    # 2. Mock Tier 3 to return this node as a match
    mock_resolve.return_value = {
        "node_key": target_key,
        "company_name": "test_target_t3",
        "confidence": 0.88,
        "tier": 3,
        "reasoning": "LLM says they are the same"
    }

    # 3. Upsert a name that won't match Tier 1 or Tier 2
    # Tier 2 won't match because name is different and no domain/CIK/shared signals
    event2 = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="test_ambiguous_alias",
        cik_number="77777",
        raw_text="totally different name but same company per LLM",
    )
    node_key = client.upsert_account(event2)

    # 4. Verify it used the target_key
    assert node_key == target_key

    # 5. Verify Alias and MERGED_FROM edge with metadata
    alias_key = tier1_resolve("test_ambiguous_alias")["hash"]
    rows = client._run(
        """
        MATCH (alias:Alias {node_key: $ak})-[r:MERGED_FROM]->(target:Account) 
        RETURN r.tier AS tier, r.confidence AS conf, r.reasoning AS reason
        """,
        {"ak": alias_key},
    )
    assert len(rows) == 1
    assert rows[0]["tier"] == 3
    assert rows[0]["conf"] == 0.88
    assert rows[0]["reason"] == "LLM says they are the same"
