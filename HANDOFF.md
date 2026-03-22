# Sprint Handoff Notes

## Sprint Completed
Sprint 11 (Week 2, Day 5) — 2026-03-22

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
- Salesforce + Zendesk generators; 47 parametrised tests

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
- Moved `record_event_received()` into `_on_change()` so measurement spans only parse + Bolt write
- Added `_submitted_ts` dict for connector→handler transit time (`fetch_ms`, debug only)
- Verified latency profile: parse ~0.1ms, Bolt write warm 1–2ms, P50 ~15s
- CLAUDE.md: added `## Verified Latency Profile`; headline "Sub-30s context freshness, sub-2ms write latency"

### Sprint 11 — Cleanup + Tier-1 Deterministic Resolver (this sprint)

#### Part A — Cleanup
- **A.1 — LATENCY log**: Confirmed `record_event_received()` already uses `event.company_name`
  (parsed + normalized name), not raw title. No code change needed.
- **A.2 — Signal accuracy**: Fixed all `_SIGNAL_PATTERNS` Item codes in `sec_ingestion.py`:
  - Added `Item 1.02` → `CONTRACT_RENEWAL_AT_RISK` (was missing entirely)
  - Fixed `Item 5.02` → `Item 2.05` for `EXECUTIVE_DEPARTURE` (was wrong)
  - Fixed `Item 4.02` → `Item 2.06` for `EARNINGS_MISS` (was wrong)
  - Added `Item 3.01` → `DELISTING_RISK` (new, using `DELISTING_RISK` enum value)
  - Added `DELISTING_RISK` to `RiskSignal` enum in `models/account_event.py`
- **A.3 — Duplicate check**: Memgraph had 0 duplicates before pipeline run.
  After pipeline run with new hash-keyed schema, 3 schema-collision duplicates appeared
  (old `company_name`-keyed nodes + new `node_key`-keyed nodes for same companies).
  One-time migration script backfilled `node_key` on 76 old nodes and deleted 4 stale
  shadow nodes. Final state: **0 duplicates, 116 Account nodes, all with `node_key`**.

#### Part B — Tier-1 Deterministic Resolver
- **`pipelines/resolver/tier1_deterministic.py`**:
  - `normalize(name)`: lowercase → strip whitespace → remove `.` and `,` →
    strip legal suffixes (whole-word: inc, llc, corp, ltd, limited, plc, co,
    incorporated, holdings, group, technologies, systems, solutions) →
    collapse whitespace
  - `deterministic_hash(normalized_name)`: SHA256 hex digest, first 16 chars
  - `resolve(name)`: returns `{original, normalized, hash, tier: 1}`
  - Uses only stdlib (`hashlib`, `re`) — zero new dependencies
- **`pipelines/resolver/__init__.py`**: created (package marker)
- **`graph/memgraph_client.py`**: updated `upsert_account` and `_upsert_event_inner`
  - MERGE key changed from `{company_name}` to `{node_key}` (SHA256 hash)
  - Node stores: `node_key`, `original_name`, `normalized_name`,
    `company_name` (= normalized, kept for read-query compatibility)
- **`tests/test_tier1.py`**: 12 tests covering normalize, hash stability,
  resolve structure, all 5 required name variants

## What Broke and How It Was Fixed

| Problem | Fix |
|---|---|
| `feedparser` returned 0 entries from SEC | Added `User-Agent` header |
| Default `.venv` is Python 3.14 — no pyarrow wheels | Use `.venv312/` (Python 3.12) |
| `.venv312/bin/pip` broken after project rename | Use `python3.12 -m pip` for installs; `.venv312/bin/python -m pip` for freeze |
| Memgraph requires `admin/admin` auth | Probed both auth configs |
| `neo4j` driver not in requirements | Installed + frozen |
| CIK parsed from URL path (unreliable) | Parse from Atom title directly |
| `AccountEvent.timestamp` set to ingest time | Set from `entry.updated` ISO string |
| `latency_tracker` in-process singleton — dashboard sees 0 events | Flush to `$TMPDIR/akf_latency_stats.json` |
| `record_event_received()` passed raw title as company name | Moved call to after `_parse_atom_title()` |
| Latency P50 showed 810–2434ms despite 1–2ms Bolt writes | Moved `record_event_received()` into `_on_change()`; `fetch_ms` excluded from measurement |
| EXECUTIVE_DEPARTURE matching Item 5.02 instead of 2.05 | Fixed regex in `_SIGNAL_PATTERNS` |
| EARNINGS_MISS matching Item 4.02 instead of 2.06 | Fixed regex in `_SIGNAL_PATTERNS` |
| Old schema (company_name MERGE key) + new schema (node_key MERGE key) created 3 duplicates | One-time migration: backfilled node_key on old nodes, deleted stale shadows |
| `python3.12 -m pip freeze` pointed at system Python, not venv | Use `.venv312/bin/python -m pip freeze` for requirements capture |

## Real Output Observed

```
pytest tests/ -q
79 passed in 0.94s

pytest tests/test_tier1.py -v
12 passed in 0.04s

# normalize() output
"Apple Inc."          → "apple"
"APPLE INCORPORATED"  → "apple"
"Apple, Inc."         → "apple"
"iSpecimen Inc."      → "ispecimen"
"Applied Digital Corp." → "applied digital"

# Duplicate Cypher query — before pipeline run
No duplicates (count > 1) found.

# Duplicate Cypher query — after pipeline run + migration
No duplicates — 0 rows returned.
Total Account nodes: 116  |  Nodes without node_key: 0

# Verified latency profile (unchanged from Sprint 10)
BOLT_WRITE company=aeluma elapsed_ms=2
Bolt write warm: 1–2ms steady-state
```

## Known Issues (Sprint 12 Cleanup)
- `_submitted_ts` dict grows unboundedly if entries are submitted but `_on_change`
  never fires (e.g. Pathway drops them). Low risk given dedup, but worth a TTL eviction.
- Debug breakdown (`[DEBUG #N]`) only prints for first 3 events — remove or gate
  behind an env flag.
- `get_account_context()` and other read methods in `memgraph_client.py` still query
  on `company_name` (now normalized name). They work but should eventually query on
  `node_key` for correctness. Low priority while `company_name` is kept in sync.

## Next Sprint Goal

**Sprint 12 — Risk scoring layer (`scoring/account_health.py`)**
- Implement weighted risk score stored as `a.risk_score` in Memgraph:
  - TAKEOVER_BID = 40
  - EXECUTIVE_DEPARTURE = 30
  - EARNINGS_MISS = 20
  - CRITICAL_SUPPORT = 15
  - CONTRACT_RENEWAL_AT_RISK = 10
  - DELISTING_RISK = 25  (suggested; confirm weight)
  - Clamp to [0, 100]
- Add `tests/test_signal_extraction.py` with fixtures for each Item code
  (SEC summary text containing "Item 1.02", "Item 2.01", etc.) verifying correct
  `RiskSignal` is extracted
- Optionally: add TTL eviction on `_submitted_ts` dict and gate `[DEBUG #N]`
  behind `AKF_DEBUG=1` env var
