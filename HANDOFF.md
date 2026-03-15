# Sprint Handoff Notes

## Sprint Completed
Sprint 8 (Week 2, Day 2) — 2026-03-15

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

### Sprint 7 — Cypher query layer + Agent Context API
- 4 new read methods added to `graph/memgraph_client.py`:
  - `get_account_context(company_name)`: returns 7-key dict with company info, risk signals,
    recent events, and `context_age_seconds` computed from `last_updated` ISO timestamp
  - `get_high_risk_accounts()`: returns accounts ordered by signal count DESC, max 20
  - `get_accounts_updated_since(seconds_ago)`: Python-side ISO date filter (Memgraph lacks APOC)
  - `search_accounts(query)`: case-insensitive substring search, limit 10
- New `graph/context_api.py`: LLM-facing `get_agent_context(company_name) -> str`
  - Formats an "ACCOUNT INTELLIGENCE REPORT" with freshness label (LIVE/RECENT/STALE)
  - `freshness_label(age_seconds)` extracted as a pure testable function
- New `tests/test_context_api.py`: 4 integration tests, all passing (0.89s)
- Critical schema fix: sprint spec incorrectly referenced `s.signal_type` — actual
  property is `s.name`; all Cypher queries use `s.name`

### Sprint 8 — SEC feed URL + entry parsing fixes
- Updated `ATOM_FEED_URL`: bumped `count=20` → `count=40`, added `search_text=` param
- Fixed `_ATOM_TITLE_RE`: now captures both company name (group 1) AND CIK (group 2)
  directly from title `"8-K - CompanyName (CIK) (Filer)"` — previously CIK was
  unreliably parsed from the URL path `/edgar/data/<CIK>/`
- Replaced `_atom_company_name()` + `_atom_cik()` with single `_parse_atom_title()`
- Added `filing_date` field (from `entry.updated`) to atom/EFTS dicts, `RawEntrySchema`,
  and `AccountEvent.timestamp` — events now carry the actual SEC filing date, not
  ingest time
- CLAUDE.md: documented SEC 8-K Item codes → RiskSignal mapping (Items 1.02, 2.01,
  2.05, 2.06, 3.01)

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
| CIK parsed from URL path (unreliable, stripped by index page redirect) | Parse from Atom title directly via updated regex |
| `AccountEvent.timestamp` set to ingest time | Set from `entry.updated` ISO string |

## Real Output Observed

```
pytest tests/test_context_api.py -v
4 passed in 0.89s

pytest tests/ -v
62 passed in 0.91s

get_agent_context("carbonite"):
ACCOUNT INTELLIGENCE REPORT
Company: carbonite
Last Updated: 2026-03-15T17:21:17.840941+00:00 (1868 seconds ago)
Risk Signals: None detected
Recent Events (13 total):
- Carbonite Inc filed 8-K on 2016-05-03. Items: 2.02, 7.01, 9.01. Accession: 0001340127-16-000175
- Carbonite Inc filed 8-K on 2016-02-04. Items: 2.02, 5.02, 7.01, 8.01, 9.01. Accession: 0001340127-16-000116
- Carbonite Inc filed 8-K on 2016-08-02. Items: 2.02, 7.01, 9.01. Accession: 0001340127-16-000212
Context Freshness: STALE (1868s)

Parsed AccountEvents from live feed (Sprint 8):
company: multisensor ai holdings  cik: 0001863990  timestamp: 2026-03-13 17:30:01-04:00  signals: []
company: applied digital           cik: 0001144879  timestamp: 2026-03-13 17:29:08-04:00  signals: [EXECUTIVE_DEPARTURE]
company: tivic health systems      cik: 0001787740  timestamp: 2026-03-13 17:27:44-04:00  signals: []
```

Graph write latency (warm Bolt connection): **0–1ms** per upsert.

## Next Sprint Goal

**Sprint 9 — Risk signal accuracy: Item-code mapping**
- Update `_SIGNAL_PATTERNS` in `sec_ingestion.py` to use correct 8-K Item codes
  per CLAUDE.md mapping:
  - Item 1.02 → CONTRACT_RENEWAL_AT_RISK
  - Item 2.01 → TAKEOVER_BID
  - Item 2.05 → EXECUTIVE_DEPARTURE (currently matching Item 5.02 — wrong item number)
  - Item 2.06 → EARNINGS_MISS
  - Item 3.01 → EARNINGS_MISS (nearest proxy until DELISTING_RISK added in Month 2)
- Add `tests/test_signal_extraction.py` with fixtures covering each Item code
- Implement `scoring/account_health.py`: weighted signal score stored as `a.risk_score`
  in Memgraph (TAKEOVER_BID=40, EXECUTIVE_DEPARTURE=30, EARNINGS_MISS=20,
  CRITICAL_SUPPORT=15, CONTRACT_RENEWAL_AT_RISK=10, clamped to [0,100])
