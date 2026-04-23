import pytest
import time
from datetime import datetime, timezone
from models.account_event import AccountEvent, EventSource, RiskSignal
from graph.memgraph_client import MemgraphClient
from graph.context_api import get_agent_context

@pytest.fixture
def client():
    client = MemgraphClient()
    # Clean up test data
    client._run("MATCH (a:Account) WHERE a.company_name STARTS WITH 'test_scoring' DETACH DELETE a")
    client._run("MATCH (alias:Alias) WHERE alias.company_name STARTS WITH 'test_scoring' DETACH DELETE alias")
    client._run("MATCH (e:Event) WHERE e.raw_text STARTS WITH 'test_scoring' DETACH DELETE e")
    yield client
    client.close()

def test_risk_scoring_integration(client):
    # 1. Create an event with multiple risk signals
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="test_scoring_corp",
        risk_signals=[RiskSignal.TAKEOVER_BID, RiskSignal.EXECUTIVE_DEPARTURE],
        raw_text="test_scoring: Material definitive agreement and departure of directors.",
        timestamp=datetime.now(timezone.utc)
    )
    
    # 2. Upsert to graph
    client.upsert_event(event)
    
    # 3. Wait a bit for eventual consistency (though Bolt is usually immediate)
    time.sleep(0.5)
    
    # 4. Get agent context and check score
    report = get_agent_context("test_scoring_corp")
    
    # TAKEOVER_BID (40) + EXECUTIVE_DEPARTURE (30) = 70
    assert "Risk Score: 70/100 (CRITICAL)" in report
    assert "Risk Signals: TAKEOVER_BID, EXECUTIVE_DEPARTURE" in report or "Risk Signals: EXECUTIVE_DEPARTURE, TAKEOVER_BID" in report

def test_risk_scoring_decay_integration(client):
    # Create an old event (e.g., 100 days ago)
    # Note: we need to manually SET the timestamp in the graph because upsert_account sets it to 'now'
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="test_scoring_old",
        risk_signals=[RiskSignal.TAKEOVER_BID],
        raw_text="test_scoring: Old takeover bid.",
        timestamp=datetime.now(timezone.utc)
    )
    
    node_key = client.upsert_account(event)
    
    # Manually set the HAS_SIGNAL timestamp to 100 days ago
    from datetime import timedelta
    old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    client._run(
        "MATCH (a:Account {node_key: $key})-[r:HAS_SIGNAL]->() SET r.timestamp = $ts",
        {"key": node_key, "ts": old_ts}
    )
    
    report = get_agent_context("test_scoring_old")
    
    # TAKEOVER_BID (40) * 0.2 (floor) = 8
    assert "Risk Score: 8/100 (STABLE)" in report
