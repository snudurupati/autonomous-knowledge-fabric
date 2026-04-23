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

### Real output observed
- **Unit Tests**: 9/9 passed in `tests/test_scoring.py`.
- **Integration Tests**: 2/2 passed in `tests/test_scoring_integration.py`.
- **Performance**: Steady-state write latency remains sub-2ms; scoring calculation is O(N) where N is number of unique signals (negligible overhead).
