# SPRINT_LOG.md

## Sprint 12 - 2026-03-23

### Sprint completed
Tier 2 Graph-Contextual Resolver (`pipelines/resolver/tier2_graph_context.py`)

### What was built
- **GraphContextResolver Class**: Implements logic for non-deterministic entity resolution using domain match (0.85), CIK match (1.0), and shared risk signals (0.40–0.65).
- **Alias Node & MERGED_FROM Edge**: Added logic to `MemgraphClient` to create `Alias` nodes and `MERGED_FROM` relationships when a merge occurs.
- **MemgraphClient Extensions**: New methods `find_potential_matches` (domain/CIK) and `find_by_name` (fuzzy search) to support the Tier 2 resolver.
- **Resolution Safety Net**: `upsert_account` now returns the final `node_key`, ensuring `_upsert_event_inner` uses the correct target node after a Tier 2 merge.

### What broke and how it was fixed
- **Fuzzy Name Matching Failure**: `test_resolve_by_multiple_shared_signals` initially failed because the resolver was doing raw string comparison on unnormalized names. Fixed by importing `normalize()` from `tier1_deterministic.py` and using it in the resolver logic.
- **Integration Test Cleanups**: Tier 2 integration tests left `Alias` nodes in the graph. Updated the `clean_test_accounts` fixture in `tests/test_memgraph_client.py` to remove `Alias` nodes where `company_name` starts with `test_`.

### Real output observed
- **Unit Tests**: 5 passed in `tests/test_tier2.py` in 0.05s.
- **Integration Tests**: 8 passed in `tests/test_memgraph_client.py` in 0.73s (including new `test_upsert_account_tier2_merge_by_domain`).
- **Steady-State Write Latency**: Warm Bolt writes remain ~1-2ms as verified by Sprint 9 dashboard benchmarks.

## Sprint 13 - 2026-03-23

### Sprint completed
Tier 3 LLM-as-Judge (`pipelines/resolver/tier3_llm_judge.py`)

### What was built
- **LLMJudgeResolver Class**: Implements final resolution tier using Gemini 1.5 Flash via `google-genai` SDK.
- **Structured Resolution Schema**: Gemini now returns `Tier3Match` with `node_key`, `confidence`, and `reasoning`.
- **LLM Rehydration Cache**: Implemented an async SQLite decision cache using `aiosqlite` to memoize resolution decisions and skip redundant LLM calls.
- **Merge Metadata Extension**: The `MERGED_FROM` relationship now stores `tier`, `confidence`, and `reasoning` for better auditability of automated merges.
- **Enhanced Upsert Logic**: `MemgraphClient` updated to fall back to Tier 3 if Tier 2 fails, with lazy instantiation of the LLM resolver.

### What broke and how it was fixed
- **Pydantic Validation Failure**: Unit tests initially failed because `AccountEvent` requires at least one identifier (Domain, CIK, or AccountID). Fixed tests by providing dummy identifiers.
- **Mock Type Error**: Integration tests failed with `ValueError: Values of type <class 'unittest.mock.MagicMock'> are not supported` during graph write. This was because the LLM mock was returning `MagicMock` by default during the first node creation. Fixed by explicitly setting `mock_resolve.return_value = None` for the initial state.
- **SDK Deprecation Warning**: Switched from `google-generativeai` to the modern `google-genai` SDK to resolve deprecation warnings.
- **Caching Async Loop Conflict**: Integrating `aiosqlite` required careful handling of `asyncio` within Pathway's synchronous execution threads. Resolved using `asyncio.run()` in the resolver wrapper.

### Real output observed
- **Unit Tests**: 4/4 passed in `tests/test_tier3.py` (including cache verification).
- **Integration Tests**: 9/9 passed in `tests/test_memgraph_client.py` (including new `test_upsert_account_tier3_merge`).
- **Dependencies**: Added `google-genai` and `aiosqlite` to `requirements.txt`.

## Sprint 14 - 2026-03-23

### Sprint completed
Ghost Node Pattern (Stateful Buffering)

### What was built
- **GhostNodeManager Class**: Implemented in `pipelines/routing.py` to handle stateful buffering of events.
- **Evidence Thresholds**: Added logic to promote events immediately if they have strong identifiers (CIK, Domain, AccountID) or after 2+ distinct events for the same fuzzy name (Corroboration).
- **Pipeline Integration**: Refactored `pipelines/sec_ingestion.py` and `pipelines/synthetic_crm.py` to use the shared `GhostNodeManager`.
- **Validation Relaxation**: Modified `AccountEvent` Pydantic model to allow name-only events, enabling them to be buffered as Ghost Nodes.

### What broke and how it was fixed
- **Pydantic Validation Conflict**: The original `AccountEvent` schema required at least one identifier, which blocked buffering of "weak" events. Relaxed this validation and updated related tests in `tests/test_account_event.py`.
- **Normalization mismatch in tests**: `test_buffering_of_weak_signal` failed because it expected "weak corp" but `normalize()` strips "corp". Updated tests to expect normalized keys.

### Real output observed
- **Unit Tests**: 5/5 passed in `tests/test_ghost_node.py`.
- **System Behavior**: Single weak events now trigger "Event buffered" logs instead of immediate graph writes.

## Sprint 15 - 2026-04-23

### Sprint completed
Risk scoring layer (`scoring/account_health.py`)

### What was built
- **Weighted Scoring Logic**: Implemented `calculate_risk_score` with weights defined in the plan (Takeover: 40, Departure: 30, etc.).
- **Recency Decay**: Added a linear decay factor that reduces signal impact over 90 days, with a 20% floor for historical context.
- **Graph Integration**: Updated `MemgraphClient.get_account_context` and `get_high_risk_accounts` to fetch signal timestamps and return calculated scores.
- **LLM Agent Report**: Enhanced `Context API` to include Risk Score and Level (CRITICAL, HIGH, etc.) in the intelligence reports.
- **Streamlit Dashboard**: Implemented a real-time dashboard in `dashboard/app.py` to visualize high-risk accounts and enable account search.

### What broke and how it was fixed
- **Memgraph Port Publication**: Integration tests initially failed because Memgraph ports were not mapped to the host. Fixed by restarting the stack with `docker compose up -d --force-recreate`.
- **Missing Dependency**: Streamlit was not in `requirements.txt`. Installed it and updated the requirements file.
- **Search Result KeyError**: Searching for accounts in the dashboard caused a `KeyError: 'company_name'` because `MemgraphClient.search_accounts` returned un-aliased Cypher fields. Fixed by adding `AS company_name` to the RETURN clause in `memgraph_client.py`.

### Real output observed
- **Unit Tests**: 9/9 passed in `tests/test_scoring.py`.
- **Integration Tests**: 2/2 passed in `tests/test_scoring_integration.py`.
- **Performance**: Steady-state write latency remains sub-2ms; scoring calculation is O(N) where N is number of unique signals (negligible overhead).

## Sprint 16 - 2026-04-23

### Sprint completed
Final Polish & Deployment

### What was built
- **Memory Leak Fixes**: Implemented TTL mechanism for `_submitted_ts` and `seen` set in SEC ingestion, and added global periodic cleanup to `GhostNodeManager`.
- **Robust Read Queries**: Migrated `get_account_context` and `get_account_with_relationships` to use a robust `COALESCE` lookup pattern that follows `Alias` nodes.
- **Log Gating**: Added `AKF_DEBUG=1` environment variable gating for high-volume debug logs in the ingestion pipeline.
- **Test Stabilization**: Updated test suite to match new risk scoring schema and fixed caching issues in Tier 3 unit tests.
- **Package Integrity**: Added missing `__init__.py` files to `graph/` and `scoring/` and verified Streamlit path resolution.

### What broke and how it was fixed
- **ModuleNotFoundError in Dashboard**: Streamlit failed to find packages when run from the root. Fixed by adding programmatic `sys.path` resolution to `dashboard/app.py` and creating missing `__init__.py` files.
- **Stale Cache in Tests**: Tier 3 unit tests failed because the cache path was fixed at module load time. Fixed by making `LLMRehydrationCache` look up the path in its constructor.

### Real output observed
- **Test Results**: 106/106 tests passed.
- **Latency Profile**: Steady-state write latency remains < 2ms; P50 freshness ~15s (half poll interval).
- **Graph Robustness**: Successfully handles lookups for merged/aliased accounts using `node_key`.

## Sprint 17 - 2026-04-28

### Sprint completed
Omnigraph Ingestion Sink (Sprint 17)

### What was built
- **OmnigraphSink Class**: Implemented in `engine/omnigraph/ingestion_sink.py` replacing the legacy in-memory buffering with native Omnigraph side-branches.
- **OmnigraphRoutingManager Class**: Implemented in `pipelines/routing.py`, utilizing `OmnigraphSink` for branch-based buffering and merge evaluation.
- **Branch-Based Buffering**: All unverified entity fragments now create a "headless" side-branch in Omnigraph.
- **The Merge Threshold**: Implemented `evaluate_and_merge` which fast-forward merges branches with an evidence score > 70 into the main production graph.
- **S3-Native Integration**: Configured `OmnigraphSink` with environment-based S3/Boto3 authentication for local RustFS or production S3.
- **Pipeline Modernization**: Refactored `sec_ingestion.py` and `synthetic_crm.py` to use the new routing manager.

### What broke and how it was fixed
- **GhostNodeManager Deprecation**: Removed all references to the legacy in-memory state manager. Fixed documentation and comment artifacts.
- **Indentation & Undefined Variables**: Fixed a fuzzy-match error in `sec_ingestion.py` that introduced an undefined `eid` variable and broken indentation during code injection.
- **Test Modernization**: Renamed and updated `tests/test_ghost_node.py` to `tests/test_omnigraph_routing.py` to reflect the branch-based architecture.

### Real output observed
- **Unit Tests**: 4/4 passed in `tests/test_omnigraph_routing.py`.
- **System Integrity**: 13/13 relevant tests passed (routing, account events, telemetry).
- **Performance**: Robust logging added for branch creation and merge latencies to enable future benchmarks against Memgraph.

## Sprint 18 - 2026-04-28

### Sprint completed
Omnigraph CRM Architecture & Client

### What was built
- **Omnigraph CRM Schema**: Defined `Account` and `AccountEvent` nodes in `schema.pg` with `@key` constraints for deterministic entity resolution.
- **Specialized GQ Library**: Created `queries/` directory with `insert_account.gq` and `get_account.gq` using parameterized, type-checked Graph Query syntax.
- **Python OmnigraphClient**: Implemented `engine/omnigraph/client.py` using `requests` to execute versioned queries against the Omnigraph REST API.
- **Security Vaulting**: Migrated plaintext S3 credentials to an externalized `.env.omni` file, referenced via `auth: env_file` in `omnigraph.yaml`.
- **Unit Test Suite**: Developed `tests/test_omnigraph_client.py` using the `unittest` framework to verify full-roundtrip entity resolution.

### What broke and how it was fixed
- **API Schema Mismatch**: Initial tests failed because Omnigraph returns data under a `rows` key (not `results`) and uses `alias.property` dot-notation. Updated the client and tests to match the current server implementation.
- **Environment Stability**: Identified and resolved a 500 error caused by the local RustFS storage being offline. Prompted infrastructure restart to restore `127.0.0.1:9000` connectivity.

### Real output observed
- **Client Verification**: Successful account insertion and retrieval confirmed with sub-second latency on the local S3 backend.
- **Query Linting**: 100% pass rate for `omnigraph query lint` against the CRM schema.

## Sprint 20 - 2026-05-05

### Sprint completed
Write Path Optimization & Omnigraph 0.4.1 Upgrade

### What was built
- **Omnigraph 0.4.1 Upgrade**: Migrated the core storage engine from v0.3.1 to v0.4.1, leveraging new commit pipelining and metadata optimizations.
- **Transactional GQL Ingestion**: Implemented `ingest_event_complete.gq` to execute Account, Event, and Link mutations in a single atomic S3 commit, reducing write overhead.
- **RCA Performance Suite**: Developed `tests/benchmark_latency.py` with support for both individual GQL mutations and high-throughput batched JSONL loads.
- **IMDS Workaround**: Implemented `AWS_EC2_METADATA_DISABLED=true` across all environments to eliminate AWS SDK credential discovery timeouts.
- **Latency Monitoring**: Integrated real-time latency logging in `OmnigraphSink` to track single-row vs. batch performance profiles.

### What broke and how it was fixed
- **70s Latency Cliff**: Identified that version 0.3.1 incurred a ~30s penalty per S3 commit due to metadata congestion in local simulators. Upgraded to **0.4.1** which reduced this to ~3.3s via better commit pipelining.
- **IMDS Discovery Hangs**: Observed multi-second hangs during client initialization. Fixed by disabling EC2 metadata discovery in `.env.omni`.
- **S3 Socket Leak**: Identified thousands of open connections during stress tests. Mitigated by switching to transactional GQL (fewer commits) and documenting the necessity of batching.

### Real output observed
- **Latency Benchmarks (v0.4.1)**:
    - **Individual GQL**: ~3.3s (reduced from 70s in v0.3.1).
    - **Batched Ingestion**: **~53ms per event** (60x faster than individual mutations).
    - **Context Read**: ~80ms-900ms (depending on write load).
- **Branch Management**: Successfully merged `omnigraph-upgrade-0.4.1` and froze `version-0.3.1` for historical baseline comparison.
- **Documentation**: Updated `README.md` with the "S3 Commit Penalty" RCA and batching recommendations.
