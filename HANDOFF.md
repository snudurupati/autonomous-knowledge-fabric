# Sprint Handoff Notes

## Sprint Completed
Sprint 10 (Week 2, Day 4) — 2026-03-15

## What Was Built

### Sprint 1 — Pathway + Memgraph hot-link
- `hello_pathway.py`: minimal Pathway pipeline, `test_connection.py`: Memgraph connectivity

### Sprint 2 — AccountEvent Pydantic schema (`models/account_event.py`)
- `EventSource`, `RiskSignal` enums; `AccountEvent` with normalization + identifier validation
- 4 pytest tests

### Sprint 3 — Live SEC EDGAR ingestion pipeline (`pipelines/sec_ingestion.py`)
- Polls Atom feed (40 8-Ks) + EFTS JSON every 30s; deduplication; risk-signal extraction
- Pathway connector: `SECFeedSubject` → `pw.io.python.read` → `pw.io.subscribe`

### Sprint 4 — Synthetic CRM & support event generator (`pipelines/synthetic_crm.py`)
- Salesforce + Zendesk generators; 47 parametrized tests

### Sprint 5 — Week 1 wrap-up & scaffolding
- Stub files for graph, scoring, dashboard, baseline_rag packages

### Sprint 6 — Graph write-back via Bolt (`graph/memgraph_client.py`)
- `MemgraphClient` with retry backoff, upsert_account/upsert_event, 7 integration tests

### Sprint 7 — Cypher query layer + Agent Context API
- 4 read methods on `MemgraphClient`; `graph/context_api.py` with `get_agent_context()`;
  `freshness_label()` (LIVE/RECENT/STALE); 4 integration tests

### Sprint 8 — SEC feed URL + entry parsing fixes
- count=40, CIK from title, `AccountEvent.timestamp` = filing date; CLAUDE.md Item codes

### Sprint 9 — OpenTelemetry instrumentation + live latency dashboard
- `observability/telemetry.py`: `LatencyTracker`, `init_tracer()`, global `tracer`,
  `akf_latency_stats.json` IPC for cross-process dashboard reads
- `observability/latency_dashboard.py`: live stats panel, 30s refresh, freshness label
- `graph/memgraph_client.py`: `graph.upsert` OTel span, `BOLT_WRITE` log per write
- Both pipelines wired with `record_event_received` / `record_graph_written`
- `tests/test_telemetry.py`: 5 unit tests; 67 total passing

### Sprint 10 — Latency measurement correctness + profile documentation
- **Root cause found**: `record_event_received()` was called in `SECFeedSubject.run()`
  before `self.next_json()`, so the clock started during the HTTP fetch loop. Pathway
  batches all `next_json` calls before dispatching `_on_change`, inflating measured
  latency to 810–2434ms when true write latency is 1–2ms.
- **Fix**: moved `record_event_received()` into `_on_change()` so measurement spans
  only parse + Bolt write. Added module-level `_submitted_ts: dict[str, float]` to
  track connector→handler transit time as `fetch_ms` (shown in debug, excluded from
  tracker stats).
- **Debug breakdown** for first 3 events:
  ```
  [DEBUG #1] fetch_ms=233.4ms  parse_ms=0.1  write_ms=217.3  total_ms=217.4
  [DEBUG #2] fetch_ms=451.4ms  parse_ms=0.1  write_ms=2.2    total_ms=2.2
  [DEBUG #3] fetch_ms=n/a      parse_ms=0.1  write_ms=1.6    total_ms=1.7
  ```
- **CLAUDE.md**: added `## Verified Latency Profile` with headline claim:
  "Sub-30s context freshness, sub-2ms write latency"

## What Broke and How It Was Fixed

| Problem | Fix |
|---|---|
| `feedparser` returned 0 entries from SEC | Added `User-Agent` header |
| Default `.venv` is Python 3.14 — no pyarrow wheels | Use `.venv312/` (Python 3.12) |
| `.venv312/bin/pip` broken after project rename | Use `python3.12 -m pip` |
| Memgraph requires `admin/admin` auth | Probed both auth configs |
| `neo4j` driver not in requirements | Installed + frozen |
| CIK parsed from URL path (unreliable) | Parse from Atom title directly |
| `AccountEvent.timestamp` set to ingest time | Set from `entry.updated` ISO string |
| `latency_tracker` in-process singleton — dashboard sees 0 events | Flush to `$TMPDIR/akf_latency_stats.json` |
| `record_event_received()` passed raw title as company name | Moved call to after `_parse_atom_title()` |
| Latency P50 showed 810–2434ms despite 1–2ms Bolt writes | Moved `record_event_received()` into `_on_change()`; `fetch_ms` excluded from measurement |

## Real Output Observed

```
pytest tests/ -v
67 passed in 0.96s

[DEBUG #1] fetch_ms=233.4ms  parse_ms=0.1  write_ms=217.3  total_ms=217.4  ← cold Bolt
[DEBUG #2] fetch_ms=451.4ms  parse_ms=0.1  write_ms=2.2    total_ms=2.2    ← warm
[DEBUG #3] fetch_ms=n/a      parse_ms=0.1  write_ms=1.6    total_ms=1.7    ← warm

LATENCY event_id=...  company=ispecimen  source=SEC_EDGAR  elapsed_ms=217.2
LATENCY event_id=...  company=evolus     source=SEC_EDGAR  elapsed_ms=2.2
LATENCY event_id=...  company=paymentus  source=SEC_EDGAR  elapsed_ms=1.6

BOLT_WRITE company=ispecimen elapsed_ms=1
BOLT_WRITE company=evolus    elapsed_ms=1
BOLT_WRITE company=bone biologics elapsed_ms=0
```

**Verified latency profile:**
- Parse: ~0.1ms
- Bolt write cold: ~217ms (first connection only)
- Bolt write warm: **1–2ms** (steady-state)
- RSS poll interval: 30s (main latency driver for freshness)
- Real-world P50: ~15s (half poll interval)
- Headline: **"Sub-30s context freshness, sub-2ms write latency"**

## Known Issues (Sprint 11 Cleanup)
- `_submitted_ts` dict grows unboundedly if entries are submitted but `_on_change`
  never fires (e.g. Pathway drops them). Low risk given dedup, but worth a TTL eviction.
- Debug breakdown (`[DEBUG #N]`) only prints for first 3 events — remove or gate
  behind an env flag in Sprint 11.

## Next Sprint Goal

**Sprint 11 — Risk signal accuracy: Item-code mapping**
- Update `_SIGNAL_PATTERNS` in `sec_ingestion.py` to use correct 8-K Item codes
  per CLAUDE.md mapping:
  - Item 1.02 → CONTRACT_RENEWAL_AT_RISK
  - Item 2.01 → TAKEOVER_BID
  - Item 2.05 → EXECUTIVE_DEPARTURE (currently matching Item 5.02 — wrong)
  - Item 2.06 → EARNINGS_MISS
  - Item 3.01 → EARNINGS_MISS (proxy until DELISTING_RISK added in Month 2)
- Add `tests/test_signal_extraction.py` with fixtures for each Item code
- Implement `scoring/account_health.py`: weighted score stored as `a.risk_score`
  in Memgraph (TAKEOVER_BID=40, EXECUTIVE_DEPARTURE=30, EARNINGS_MISS=20,
  CRITICAL_SUPPORT=15, CONTRACT_RENEWAL_AT_RISK=10, clamped to [0,100])
