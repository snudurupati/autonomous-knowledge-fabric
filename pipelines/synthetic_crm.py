# pipelines/synthetic_crm.py
# Faker-based generator emitting synthetic Salesforce + Zendesk events.

import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker

from models.account_event import AccountEvent, EventSource, RiskSignal

fake = Faker()

SEED_COMPANIES = [
    {"name": "apple", "domain": "apple.com", "account_id": "SF-001"},
    {"name": "microsoft", "domain": "microsoft.com", "account_id": "SF-002"},
    {"name": "tesla", "domain": "tesla.com", "account_id": "SF-003"},
    {"name": "jpmorgan", "domain": "jpmorgan.com", "account_id": "SF-004"},
    {"name": "walmart", "domain": "walmart.com", "account_id": "SF-005"},
]

OPPORTUNITY_STAGES = ["Negotiation", "At Risk", "Churned", "Renewal"]
CASE_PRIORITIES = ["Low", "Medium", "High", "Critical"]


class SalesforceEventGenerator:
    def generate(self, company: dict | None = None, stage: str | None = None) -> AccountEvent:
        company = company or random.choice(SEED_COMPANIES)
        stage = stage or random.choice(OPPORTUNITY_STAGES)
        arr = round(random.uniform(50_000, 2_000_000), 2)
        renewal_date = (
            datetime.now(timezone.utc) + timedelta(days=random.randint(1, 90))
        ).date()

        raw_text = json.dumps({
            "Account_ID": company["account_id"],
            "Opportunity_Stage": stage,
            "ARR": arr,
            "Contract_Renewal_Date": str(renewal_date),
        })

        risk_signals = []
        if stage in ("At Risk", "Churned"):
            risk_signals.append(RiskSignal.CONTRACT_RENEWAL_AT_RISK)

        return AccountEvent(
            source=EventSource.SALESFORCE,
            company_name=company["name"],
            company_domain=company["domain"],
            account_id=company["account_id"],
            raw_text=raw_text,
            risk_signals=risk_signals,
        )


class ZendeskEventGenerator:
    def generate(self, company: dict | None = None, priority: str | None = None) -> AccountEvent:
        company = company or random.choice(SEED_COMPANIES)
        priority = priority or random.choice(CASE_PRIORITIES)
        case_id = str(uuid.uuid4())
        escalation_time = datetime.now(timezone.utc) - timedelta(
            seconds=random.randint(0, 86_400)
        )
        sla_breach = priority == "Critical"

        raw_text = json.dumps({
            "Case_ID": case_id,
            "Account_ID": company["account_id"],
            "Case_Priority": priority,
            "Escalation_Time": escalation_time.isoformat(),
            "SLA_Breach": sla_breach,
        })

        risk_signals = []
        if priority == "Critical":
            risk_signals.append(RiskSignal.CRITICAL_SUPPORT)

        return AccountEvent(
            source=EventSource.ZENDESK,
            company_name=company["name"],
            company_domain=company["domain"],
            account_id=company["account_id"],
            raw_text=raw_text,
            risk_signals=risk_signals,
        )


def run(interval_secs: int = 10) -> None:
    sf_gen = SalesforceEventGenerator()
    zd_gen = ZendeskEventGenerator()
    generators = [sf_gen, zd_gen]
    count = 0

    while True:
        company = random.choice(SEED_COMPANIES)
        gen = generators[count % 2]
        event = gen.generate(company=company)
        count += 1
        print(f"\n=== Event #{count} ({event.source.value}) ===")
        print(event.model_dump_json(indent=2))
        time.sleep(interval_secs)


if __name__ == "__main__":
    run()
