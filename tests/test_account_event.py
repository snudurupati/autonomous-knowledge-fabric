"""Sprint 2: Tests for AccountEvent Pydantic schema."""
import pytest
from pydantic import ValidationError

from models.account_event import AccountEvent, EventSource, RiskSignal


def _base(**kwargs) -> dict:
    """Minimal valid event kwargs."""
    return {
        "source": EventSource.SEC_EDGAR,
        "raw_text": "Some filing text.",
        "cik_number": "0000320193",
        **kwargs,
    }


# --- company_name normalisation ---

def test_apple_inc_normalizes():
    event = AccountEvent(**_base(company_name="Apple Inc."))
    assert event.company_name == "apple"


def test_acme_corp_normalizes():
    event = AccountEvent(**_base(company_name="ACME CORP"))
    assert event.company_name == "acme"


# --- identifier guard ---

def test_no_identifiers_raises():
    with pytest.raises(ValidationError, match="At least one identifier"):
        AccountEvent(
            source=EventSource.SALESFORCE,
            company_name="Vandelay Industries",
            raw_text="No IDs provided.",
        )


# --- happy path ---

def test_valid_sec_event():
    event = AccountEvent(
        source=EventSource.SEC_EDGAR,
        company_name="Acme Corp",
        cik_number="0001234567",
        raw_text="Form 8-K: executive departure effective immediately.",
        risk_signals=[RiskSignal.EXECUTIVE_DEPARTURE],
        confidence_score=0.95,
    )
    assert event.source == EventSource.SEC_EDGAR
    assert event.company_name == "acme"
    assert event.cik_number == "0001234567"
    assert RiskSignal.EXECUTIVE_DEPARTURE in event.risk_signals
    assert event.confidence_score == 0.95
    assert event.event_id  # auto-generated UUID
