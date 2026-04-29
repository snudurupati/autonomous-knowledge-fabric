# autonomous-knowledge-fabric — CLAUDE.md

## Project Mission
Reference architecture for real-time Account Intelligence using Pathway (stream processing) + Omnigraph (versioned, S3-native knowledge graph).

## Core Architecture & Strict Omnigraph Constraints
* **Engine:** Omnigraph (S3-native graph database) replacing Memgraph. Local RustFS S3 simulator running on `127.0.0.1:9000`. Omnigraph Server on `127.0.0.1:8080`.
* **NO RAW HTTP:** Never use `requests.post()` to send raw queries to the Omnigraph API.
* **NO CYPHER:** Omnigraph uses a proprietary Graph Query (GQ) syntax, not Cypher. Do not write `MATCH` or `CREATE` statements.
* **CONFIGURATION DRIVEN:** The project relies on an `omnigraph.yaml` file at the root. Do not hardcode endpoint URLs in Python files.
* **LINKED QUERIES ONLY:** All database operations (`insert`, `search`, `merge`) must be written in dedicated `.gq` files located in the `queries/` directory. 
* **CUSTOM HTTP WRAPPER:** There is no official Python SDK. Use `requests` to build a custom client in `engine/omnigraph/client.py`. 
* **PAYLOAD SCHEMA:** All requests to `/read` or `/change` must send a JSON payload with `query_source` (the raw `.gq` string), `branch` (string), and `params` (dict). Read `.gq` files from disk to populate `query_source`.:w

## Omnigraph Branching Conventions (Sprint 17+)
* **Headless Branches:** Every unverified entity fragment MUST be ingested into a unique side-branch (e.g., `fragment/<uuid>`).
* **Merge Threshold:** Branches are only merged into `main` if the `evidence_score` exceeds 70.
* **Pollution Control:** If a branch fails the threshold, it MUST be deleted via the SDK to prevent graph pollution.

## Environment Conventions
* **Virtual Env:** Always use `.venv-omnigraph/bin/python` (Python 3.12).
* **Pip Freeze:** Use `.venv-omnigraph/bin/python -m pip freeze > requirements.txt` (never use `python3.12 -m pip freeze` as it targets the system).
* **Running Scripts:** Always run scripts as modules from project root: `python -m pipelines.script_name`

## SEC 8-K Item Codes → Risk Signals
* Item 1.01 = Material Definitive Agreement
* Item 1.02 = Termination of Material Agreement → CONTRACT_RENEWAL_AT_RISK
* Item 2.01 = Completion of Acquisition → TAKEOVER_BID
* Item 2.05 = Departure of Directors/Officers → EXECUTIVE_DEPARTURE
* Item 2.06 = Material Impairment → EARNINGS_MISS
* Item 3.01 = Delisting Notice → DELISTING_RISK
* Item 8.01 = Other Events (catch-all)

## SEC EDGAR Atom Feed Conventions
* **Dedup key:** `entry.id` — format `urn:tag:sec.gov,2008:accession-number=XXXX`
* **Filing date:** `entry.updated` — ISO 8601 with TZ offset.
* **Company name + CIK:** Parse from `entry.title` using regex `r"^[\w/\-]+ - (.+?)\s*\((\d+)\)"` (group 1 = company, group 2 = CIK). Never parse CIK from the URL path.
* **Risk signals:** Strip HTML from `entry.summary`, then keyword-match Item codes.
* `AccountEvent.timestamp` = filing date from `entry.updated`, not ingest time.

## Tier-1 Resolver Conventions
* `node_key` = `SHA256(normalize(company_name)).hexdigest()[:16]` — canonical key for all Account nodes.
* `company_name` = normalized form (lowercase, no punctuation, no legal suffixes).
* `original_name` = raw string before normalization.
* Legal suffixes stripped (whole-word): inc, llc, corp, ltd, limited, plc, co, incorporated, holdings, group, technologies, systems, solutions.

## Observability Conventions
* `latency_tracker` is an in-process singleton. Cross-process state is exchanged via `$TMPDIR/akf_latency_stats.json`.
* OTel span naming: Use `pipeline.branch_create`, `pipeline.branch_merge`, `pipeline.event`.
