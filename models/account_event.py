# models/account_event.py
# Core Pydantic schemas for SEC filings, CRM webhooks, and support events.

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Legal suffixes stripped during Tier-1 entity resolution.
_LEGAL_SUFFIXES = re.compile(
    r"\b(inc|llc|corp|ltd|limited|plc|co)\b\.?$",
    re.IGNORECASE,
)


class EventSource(str, Enum):
    SEC_EDGAR = "SEC_EDGAR"
    SALESFORCE = "SALESFORCE"
    ZENDESK = "ZENDESK"


class RiskSignal(str, Enum):
    TAKEOVER_BID = "TAKEOVER_BID"
    EARNINGS_MISS = "EARNINGS_MISS"
    EXECUTIVE_DEPARTURE = "EXECUTIVE_DEPARTURE"
    CRITICAL_SUPPORT = "CRITICAL_SUPPORT"
    CONTRACT_RENEWAL_AT_RISK = "CONTRACT_RENEWAL_AT_RISK"
    DELISTING_RISK = "DELISTING_RISK"


class AccountEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: EventSource
    company_name: str
    company_domain: Optional[str] = None
    cik_number: Optional[str] = None
    account_id: Optional[str] = None
    risk_signals: list[RiskSignal] = Field(default_factory=list)
    raw_text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("company_name")
    @classmethod
    def normalize_company_name(cls, v: str) -> str:
        v = v.strip().lower()
        v = _LEGAL_SUFFIXES.sub("", v).strip().rstrip(",").strip()
        return v

