import pytest
from datetime import datetime, timezone, timedelta
from scoring.account_health import calculate_risk_score, get_risk_level

def test_empty_signals():
    assert calculate_risk_score([]) == 0
    assert get_risk_level(0) == "LOW"

def test_basic_scoring():
    signals = [
        {"name": "TAKEOVER_BID"}, # 40
        {"name": "EXECUTIVE_DEPARTURE"} # 30
    ]
    # Total = 70
    assert calculate_risk_score(signals) == 70
    assert get_risk_level(70) == "CRITICAL"

def test_clamping():
    signals = [
        {"name": "TAKEOVER_BID"}, # 40
        {"name": "EXECUTIVE_DEPARTURE"}, # 30
        {"name": "DELISTING_RISK"}, # 25
        {"name": "EARNINGS_MISS"} # 20
    ]
    # Total = 115 -> clamped to 100
    assert calculate_risk_score(signals) == 100

def test_recency_decay_fresh():
    now = datetime.now(timezone.utc).isoformat()
    signals = [{"name": "TAKEOVER_BID", "timestamp": now}]
    assert calculate_risk_score(signals) == 40

def test_recency_decay_stale():
    # 20 days ago: (1.0 - (20-7)*(0.5/23)) = 1.0 - 13*0.0217 = 1.0 - 0.282 = 0.718
    # 40 * 0.718 = 28.72 -> 28
    stale_date = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    signals = [{"name": "TAKEOVER_BID", "timestamp": stale_date}]
    score = calculate_risk_score(signals)
    assert 27 <= score <= 30

def test_recency_decay_floor():
    # 100 days ago: 20% floor
    # 40 * 0.2 = 8
    very_stale_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    signals = [{"name": "TAKEOVER_BID", "timestamp": very_stale_date}]
    assert calculate_risk_score(signals) == 8

def test_unknown_signal():
    signals = [{"name": "UNKNOWN_SIGNAL"}]
    # Default weight 5
    assert calculate_risk_score(signals) == 5

def test_deduplication():
    signals = [
        {"name": "TAKEOVER_BID"},
        {"name": "TAKEOVER_BID"}
    ]
    # Should only count once
    assert calculate_risk_score(signals) == 40

def test_risk_levels():
    assert get_risk_level(80) == "CRITICAL"
    assert get_risk_level(50) == "HIGH"
    assert get_risk_level(30) == "ELEVATED"
    assert get_risk_level(10) == "STABLE"
    assert get_risk_level(0) == "LOW"
