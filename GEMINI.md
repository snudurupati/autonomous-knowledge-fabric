# autonomous-knowledge-fabric — CLAUDE.md

## Project Mission
Reference architecture for real-time Account Intelligence using
Pathway (stream processing) + Omnigraph (versioned knowledge graph).

## Core Use Case
Sales Director QBR scenario: detect SEC filings + CRM events
and update account risk score in <60 seconds.

## Stack
- Stream processor: Pathway (Python/Rust, single container)
- Graph Engine: Omnigraph (RustFS-backed, S3-native)
- Schema validation: Pydantic
- Entity resolution: 3-Tier (Hash → Graph Neighbor → LLM Judge)
- Observability: OpenTelemetry from Day 1
- Persistence: RustFS (Local S3 emulator for graph commits)

## Current Sprint
- [x] Sprint 17 — Omnigraph Ingestion Sink (Branch-based Buffering)

## Conventions
- All Pydantic models live in /models
- Pathway pipelines live in /pipelines
- Tests use pytest, run via `.venv-omnigraph/bin/pytest tests/`
- **Python Environment**: Use `.venv-omnigraph/bin/python` for all Omnigraph-pivot tasks.
- **Pip Freeze**: Use `.venv-omnigraph/bin/python -m pip freeze > requirements.txt`.
- **S3 Connectivity**: OmnigraphSink requires `S3_ENDPOINT`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` for RustFS connectivity.
- `timeout` is not available on macOS (GNU coreutils only) — use Python-native loop control instead of shell `timeout`

## Omnigraph Branching Conventions (Sprint 17+)
- **Headless Branches**: Every unverified entity fragment MUST be ingested into a unique side-branch (e.g., `fragment/<uuid>`).
- **Merge Threshold**: Branches are only merged into `main` if the `evidence_score` exceeds **70**.
- **Pollution Control**: If a branch fails the merge threshold or is rejected by a resolver, it MUST be deleted (requests.delete) to prevent graph pollution.
- **Persistence**: All writes are S3-native; ensure the local RustFS server is running (default `http://127.0.0.1:9000`).

## Running Scripts
- Always run scripts as modules from project root:
  `python -m pipelines.script_name`
- **Dashboard:** Run Streamlit using the Omnigraph-compatible venv:
  `.venv-omnigraph/bin/streamlit run dashboard/app.py`

## SEC 8-K Item Codes → Risk Signals
Item 1.01 = Material Definitive Agreement
Item 1.02 = Termination of Material Agreement  → CONTRACT_RENEWAL_AT_RISK
Item 2.01 = Completion of Acquisition          → TAKEOVER_BID
Item 2.05 = Departure of Directors/Officers    → EXECUTIVE_DEPARTURE
Item 2.06 = Material Impairment               → EARNINGS_MISS
Item 3.01 = Delisting Notice → DELISTING_RISK
Item 8.01 = Other Events (catch-all)

## SEC EDGAR Atom Feed Conventions
- Dedup key: `entry.id` — format `urn:tag:sec.gov,2008:accession-number=XXXX`
- Filing date: `entry.updated` — ISO 8601 with TZ offset, e.g. `2026-03-13T17:30:01-04:00`
- Company name + CIK: parse from `entry.title` using `_parse_atom_title()`
  - Title format: `"8-K - CompanyName (CIK) (Filer)"`
  - Regex: `r"^[\w/\-]+ - (.+?)\s*\((\d+)\)"` — group 1 = company, group 2 = CIK
- Risk signals: strip HTML from `entry.summary`, then keyword-match Item codes
- `AccountEvent.timestamp` = filing date from `entry.updated`, not ingest time

## Observability Conventions
- `latency_tracker` is an in-process singleton. Cross-process state is exchanged
  via `$TMPDIR/akf_latency_stats.json`.
- OTel span naming: `pipeline.branch_create`, `pipeline.branch_merge`, `pipeline.event`.
- Latency benchmarks: record `write_latency_ms` for branch creation and `merge_latency_ms` for promotions.

## Tier-1 Resolver Conventions (Sprint 11)
- `node_key` = `SHA256(normalize(company_name)).hexdigest()[:16]` — canonical MERGE key.
- Legal suffixes stripped: inc, llc, corp, ltd, limited, plc, co, incorporated, holdings, group, technologies, systems, solutions.

## Bot Identity
- **Git Name**: Gemini CLI
- **Git Email**: gemini-cli[bot]@users.noreply.github.com
