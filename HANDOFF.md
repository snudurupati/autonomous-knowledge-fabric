# Sprint Handoff Notes

## Sprint Completed
Sprint 6 (Week 2, Day 1) — 2026-03-15

## What Was Built

### Sprint 1 — Pathway + Memgraph hot-link
- `hello_pathway.py`: minimal Pathway pipeline printing 3 rows (proves Pathway works)
- `test_connection.py`: connects to Memgraph on port 7687, runs `RETURN 1` query

### Sprint 2 — AccountEvent Pydantic schema (`models/account_event.py`)
- `EventSource` enum: SEC_EDGAR, SALESFORCE, ZENDESK
- `RiskSignal` enum: TAKEOVER_BID, EARNINGS_MISS, EXECUTIVE_DEPARTURE, CRITICAL_SUPPORT, CONTRACT_RENEWAL_AT_RISK
- `AccountEvent` model with `company_name` normalization and identifier validation
- 4 pytest tests: 4 passed

### Sprint 3 — Live SEC EDGAR ingestion pipeline (`pipelines/sec_ingestion.py`)
- Polls Atom feed (20 8-Ks) + EFTS JSON (hostile takeover) every 30 seconds
- Deduplicates by `entry_id`, extracts `AccountEvent` with risk-signal keyword matching
- Pathway connector: `SECFeedSubject` → `pw.io.python.read` → `pw.io.subscribe`

### Sprint 4 — Synthetic CRM & support event generator (`pipelines/synthetic_crm.py`)
- 5 seed companies (Apple, Microsoft, Tesla, JPMorgan, Walmart)
- `SalesforceEventGenerator` + `ZendeskEventGenerator` alternating every 10 seconds
- 47 parametrized pytest tests: 47 passed

### Sprint 5 — Week 1 wrap-up & scaffolding
- Published Week 1 Substack post, updated README and CLAUDE.md
- Created stub files: `graph/memgraph_client.py`, `scoring/account_health.py`,
  `dashboard/app.py`, `baseline_rag/nightly_batch.py`

### Sprint 6 — Graph write-back via Bolt (`graph/memgraph_client.py`)
- `MemgraphClient` class connecting to Memgraph on `bolt://localhost:7687` (`admin/admin`)
- 3-retry backoff on `ServiceUnavailable` / `SessionExpired`
- `upsert_account(event)`: `MERGE` on `company_name`, sets domain/cik/account_id/source/last_updated,
  creates `RiskSignal` nodes + `HAS_SIGNAL` edges with timestamp
- `upsert_event(event)`: calls `upsert_account` + creates raw `Event` node with `FILED` edge
- `get_account_with_relationships(company_name)`: returns account + all 1-hop rels as dict
- `pipelines/sec_ingestion.py`: calls `client.upsert_event()` per AccountEvent, prints
  `Graph updated: {company} [{signals}] in {ms}ms`
- `pipelines/synthetic_crm.py`: same write-back, `write_graph=True` by default
- `tests/test_memgraph_client.py`: 7 integration tests against live Memgraph

## What Broke and How It Was Fixed

| Problem | Fix |
|---|---|
| `feedparser` returned 0 entries from SEC | Added `User-Agent` header |
| `docker-compose.yml` was a shell script | Rewrote to proper YAML |
| `pw.debug.table_from_markdown` failed with multi-word fields | Switched to `table_from_pandas` |
| Default `.venv` is Python 3.14 — no pyarrow wheels | Use `.venv312/` (Python 3.12) |
| `.venv312/bin/pip` broken after project rename | Use `python3.12 -m pip` |
| `.venv312` accidentally committed (160MB binary) | `git filter-repo` + `.gitignore`, force-push |
| Memgraph requires `admin/admin` auth (not no-auth) | Probed both auth configs before writing client |
| `time` import shadowed by `time` parameter in `_on_change` | Aliased as `import time as time_module` |
| `.venv312` wiped by `git filter-repo` history rewrite | Recreated from `requirements.txt` |
| `neo4j` driver not in requirements | Installed + frozen (`neo4j==6.1.0`) |

## Real Output Observed

```
pytest tests/test_memgraph_client.py -v
7 passed in 0.56s

pytest tests/ -v
58 passed in 0.62s

Graph updated: patron systems [none] in 200ms     ← cold Bolt connection
Graph updated: cb bancshares inc/hi [none] in 1ms
Graph updated: wyndham hotels & resorts [none] in 0ms
Graph updated: ebr systems [EARNINGS_MISS] in 1ms
Graph updated: applied digital [EXECUTIVE_DEPARTURE] in 0ms
Graph updated: new mountain finance [TAKEOVER_BID] in 0ms
```

Graph write latency (warm connection): **0–1ms** per upsert. Well under 60s target.

## Next Sprint Goal

**Sprint 7 — Account health scoring + Streamlit dashboard (Week 2, Day 2)**
- Implement `scoring/account_health.py`: weighted 4-signal score
  - TAKEOVER_BID: 40pts, EXECUTIVE_DEPARTURE: 30pts, EARNINGS_MISS: 20pts,
    CRITICAL_SUPPORT: 15pts, CONTRACT_RENEWAL_AT_RISK: 10pts
  - Score clamped to [0, 100], stored back to Memgraph as `a.risk_score`
- Wire scorer into both pipeline `_on_change` / `run()` callbacks
- Implement `dashboard/app.py`: Streamlit table of accounts sorted by risk_score,
  with a "Context Freshness" counter (seconds since last graph update)
- Add `tests/test_account_health.py` with unit tests for score calculation
