# Sprint Handoff Notes

## Sprint Completed
Sprint 3 (Week 1, Day 3) — 2026-03-07

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
- `models/__init__.py` added
- 4 pytest tests: 4 passed, 0 failed (0.04s)

### Sprint 3 — Live SEC EDGAR ingestion pipeline (`pipelines/sec_ingestion.py`)
- Polls two SEC feeds every 30 seconds:
  - Atom feed (20 current 8-Ks): `https://www.sec.gov/cgi-bin/browse-edgar?...&output=atom`
  - EFTS JSON search (hostile takeover keyword): `https://efts.sec.gov/LATEST/search-index?...`
- Deduplicates by `entry_id` across polls
- Extracts `AccountEvent` per filing with risk-signal keyword matching
- Pathway connector: `SECFeedSubject(pw.io.python.ConnectorSubject)` → `pw.io.python.read` → `pw.io.subscribe`
- `docker-compose.yml` fixed from shell-script corruption to valid YAML

## What Broke and How It Was Fixed

| Problem | Fix |
|---|---|
| `feedparser` returned 0 entries from SEC | Added `User-Agent: stream-graph-rag research@example.com` header (SEC rate-limit policy) |
| `docker-compose.yml` was a shell script, not YAML | Rewrote to proper YAML; obsolete `version:` key warns but is harmless |
| `pw.debug.table_from_markdown` failed with multi-word fields | Switched to `pw.debug.table_from_pandas` |
| Default `.venv` is Python 3.14 — lacks pyarrow wheels | Use `.venv312/` (Python 3.12) for all commands |

## Real Output Observed

```
pytest tests/ -v
4 passed in 0.04s

[poll] fetched 20 entries, 20 new, 20 total seen
=== AccountEvent #1 ===
{
  "event_id": "...",
  "source": "SEC_EDGAR",
  "company_name": "reservoir media",   ← normalized from "Reservoir Media, Inc."
  "cik_number": "1824403",
  "risk_signals": [],
  "raw_text": "...",
  ...
}
```

Latency from SEC filing to printed `AccountEvent`: < 1 second (within a single poll cycle; end-to-end SEC → Memgraph not yet wired).

## Next Sprint Goal

**Sprint 4 — Graph write-back + risk score**
- Wire `AccountEvent` output into Memgraph via `graph/` client helpers
- `MERGE (a:Account {cik: $cik}) SET a.risk_score = $score, a.updated_at = $ts`
- Add `graph/memgraph_client.py` with connection pooling (pymgclient or neo4j-driver)
- End-to-end latency target: SEC filing → Memgraph node update < 60 seconds
- Add integration test: `tests/test_graph_write.py`
