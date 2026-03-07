# tests/test_synthetic_crm.py

import json

import pytest

from models.account_event import AccountEvent, EventSource, RiskSignal
from pipelines.synthetic_crm import (
    SEED_COMPANIES,
    SalesforceEventGenerator,
    ZendeskEventGenerator,
)

sf_gen = SalesforceEventGenerator()
zd_gen = ZendeskEventGenerator()


def test_salesforce_at_risk_has_signal():
    event = sf_gen.generate(company=SEED_COMPANIES[0], stage="At Risk")
    assert RiskSignal.CONTRACT_RENEWAL_AT_RISK in event.risk_signals


def test_salesforce_churned_has_signal():
    event = sf_gen.generate(company=SEED_COMPANIES[0], stage="Churned")
    assert RiskSignal.CONTRACT_RENEWAL_AT_RISK in event.risk_signals


def test_salesforce_negotiation_no_signal():
    event = sf_gen.generate(company=SEED_COMPANIES[0], stage="Negotiation")
    assert RiskSignal.CONTRACT_RENEWAL_AT_RISK not in event.risk_signals


def test_zendesk_critical_has_signal():
    event = zd_gen.generate(company=SEED_COMPANIES[1], priority="Critical")
    assert RiskSignal.CRITICAL_SUPPORT in event.risk_signals


def test_zendesk_high_no_signal():
    event = zd_gen.generate(company=SEED_COMPANIES[1], priority="High")
    assert RiskSignal.CRITICAL_SUPPORT not in event.risk_signals


def test_zendesk_critical_sla_breach():
    event = zd_gen.generate(company=SEED_COMPANIES[0], priority="Critical")
    payload = json.loads(event.raw_text)
    assert payload["SLA_Breach"] is True


def test_zendesk_non_critical_no_sla_breach():
    event = zd_gen.generate(company=SEED_COMPANIES[0], priority="High")
    payload = json.loads(event.raw_text)
    assert payload["SLA_Breach"] is False


@pytest.mark.parametrize("company", SEED_COMPANIES)
@pytest.mark.parametrize("stage", ["Negotiation", "At Risk", "Churned", "Renewal"])
def test_all_salesforce_events_valid(company, stage):
    event = sf_gen.generate(company=company, stage=stage)
    assert isinstance(event, AccountEvent)
    assert event.source == EventSource.SALESFORCE


@pytest.mark.parametrize("company", SEED_COMPANIES)
@pytest.mark.parametrize("priority", ["Low", "Medium", "High", "Critical"])
def test_all_zendesk_events_valid(company, priority):
    event = zd_gen.generate(company=company, priority=priority)
    assert isinstance(event, AccountEvent)
    assert event.source == EventSource.ZENDESK
