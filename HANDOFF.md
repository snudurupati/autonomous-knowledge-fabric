# Sprint Handoff Notes

## Sprint Completed
Sprint 4 (Week 1, Day 4) — 2026-03-07

## What Was Built

### Sprint 1 — Pathway + Memgraph hot-link
- `hello_pathway.py`: minimal Pathway pipeline printing 3 rows (proves Pathway works)
- `test_connection.py`: connects to Memgraph on port 7687, runs `RETURN 1` query

### Sprint 2 — AccountEvent Pydantic schema (`models/account_event.py`)
- `EventSource` enum: SEC_EDGAR, SALESFORCE, ZENDESK
- `RiskSignal` enum: TAKEOVER_BID, EARNINGS_MISS, EXECUTIVE_DEPARTURE, CRITICAL_SUPPORT, CONTRACT_RENEWAL_AT_RISK
- `AccountEvent` model with:
  - `company_name` normalization (strip, lowercase, remove legal suffixes via regex)
  - `model_validator` requiring at least one of: `company_domain`, `cik_number`, `account_id`
- 4 pytest tests: 4 passed, 0 failed (0.04s)

### Sprint 3 — Live SEC EDGAR ingestion pipeline (`pipelines/sec_ingestion.py`)
- Polls two SEC feeds every 30 seconds:
  - Atom feed (20 current 8-Ks): `https://www.sec.gov/cgi-bin/browse-edgar?...&output=atom`
  - EFTS JSON search (hostile takeover keyword): `https://efts.sec.gov/LATEST/search-index?...`
- Deduplicates by `entry_id` across polls
- Extracts `AccountEvent` per filing with risk-signal keyword matching
- Pathway connector: `SECFeedSubject(pw.io.python.ConnectorSubject)` → `pw.io.python.read` → `pw.io.subscribe`

### Sprint 4 — Synthetic CRM & support event generator (`pipelines/synthetic_crm.py`)
- `SEED_COMPANIES`: 5 real public companies (Apple, Microsoft, Tesla, JPMorgan, Walmart) with domain + Salesforce account ID
- `SalesforceEventGenerator`: emits `AccountEvent` with `Opportunity_Stage`, `ARR`, `Contract_Renewal_Date`; fires `CONTRACT_RENEWAL_AT_RISK` when stage is "At Risk" or "Churned"
- `ZendeskEventGenerator`: emits `AccountEvent` with `Case_ID`, `Case_Priority`, `Escalation_Time`, `SLA_Breach`; fires `CRITICAL_SUPPORT` when priority is "Critical"
- `run()` loop alternates SF/ZD every 10 seconds, random company per event
- `tests/test_synthetic_crm.py`: 47 tests (7 unit + 40 parametrized across all companies × all stages/priorities)

## What Broke and How It Was Fixed

| Problem | Fix |
|---|---|
| `feedparser` returned 0 entries from SEC | Added `User-Agent: stream-graph-rag research@example.com` header |
| `docker-compose.yml` was a shell script, not YAML | Rewrote to proper YAML |
| `pw.debug.table_from_markdown` failed with multi-word fields | Switched to `pw.debug.table_from_pandas` |
| Default `.venv` is Python 3.14 — lacks pyarrow wheels | Use `.venv312/` (Python 3.12) for all commands |
| `faker` not installed in `.venv312` | `pip install faker` (now in requirements.txt as `Faker==40.8.0`) |

## Real Output Observed

```
pytest tests/ -v
51 passed in 0.09s

=== Event #1 (SALESFORCE) ===
{
  "source": "SALESFORCE", "company_name": "jpmorgan",
  "account_id": "SF-004", "risk_signals": [],
  "raw_text": "{\"Opportunity_Stage\": \"Negotiation\", \"ARR\": 924498.16, \"Contract_Renewal_Date\": \"2026-05-06\"}"
}

=== Event #2 (ZENDESK) ===
{
  "source": "ZENDESK", "company_name": "tesla",
  "account_id": "SF-003", "risk_signals": [],
  "raw_text": "{\"Case_Priority\": \"Low\", \"SLA_Breach\": false}"
}

=== Event #3 (SALESFORCE) ===
{
  "source": "SALESFORCE", "company_name": "tesla",
  "account_id": "SF-003", "risk_signals": ["CONTRACT_RENEWAL_AT_RISK"],
  "raw_text": "{\"Opportunity_Stage\": \"At Risk\", \"ARR\": 1552063.51, \"Contract_Renewal_Date\": \"2026-05-15\"}"
}
```

Event emission latency: ~0ms (in-process generation, no I/O). Inter-event interval: 10 seconds.

## Next Sprint Goal

**Sprint 5 — Graph write-back + risk score**
- Wire both `sec_ingestion.py` and `synthetic_crm.py` outputs into Memgraph
- `graph/memgraph_client.py`: connection pooling via `pymgclient`, `upsert_account()` helper
- Cypher: `MERGE (a:Account {cik: $cik}) SET a.risk_score = $score, a.updated_at = $ts`
- Add `RiskScoreCalculator`: weighted score from risk_signals list
- End-to-end latency target: event emitted → Memgraph node updated < 60 seconds
- Integration test: `tests/test_graph_write.py`
