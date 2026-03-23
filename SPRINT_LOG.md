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
- **Merge Metadata Extension**: The `MERGED_FROM` relationship now stores `tier`, `confidence`, and `reasoning` for better auditability of automated merges.
- **Enhanced Upsert Logic**: `MemgraphClient` updated to fall back to Tier 3 if Tier 2 fails, with lazy instantiation of the LLM resolver.

### What broke and how it was fixed
- **Pydantic Validation Failure**: Unit tests initially failed because `AccountEvent` requires at least one identifier (Domain, CIK, or AccountID). Fixed tests by providing dummy identifiers.
- **Mock Type Error**: Integration tests failed with `ValueError: Values of type <class 'unittest.mock.MagicMock'> are not supported` during graph write. This was because the LLM mock was returning `MagicMock` by default during the first node creation. Fixed by explicitly setting `mock_resolve.return_value = None` for the initial state.
- **SDK Deprecation Warning**: Switched from `google-generativeai` to the modern `google-genai` SDK to resolve deprecation warnings.

### Real output observed
- **Unit Tests**: 3/3 passed in `tests/test_tier3.py`.
- **Integration Tests**: 9/9 passed in `tests/test_memgraph_client.py` (including new `test_upsert_account_tier3_merge`).
- **Dependencies**: Added `google-genai` to `requirements.txt`.
