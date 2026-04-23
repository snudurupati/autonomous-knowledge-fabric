# Project Plan: Autonomous Knowledge Fabric

## Context
- **Last Session:** Sprint 16 complete (2026-04-23)
- **Current Goal:** Sprint 17 — RAG Baseline Comparison
- **Tech Stack:** Pathway (stream processor), Memgraph (graph DB), Pydantic, OpenTelemetry, Streamlit
- **Branch:** week-2

## Completed Sprints

- [x] Sprint 1 — Pathway + Memgraph hot-link (`hello_pathway.py`, `test_connection.py`)
- [x] Sprint 2 — AccountEvent Pydantic schema (`models/account_event.py`), EventSource/RiskSignal enums, 4 tests
- [x] Sprint 3 — Live SEC EDGAR ingestion pipeline (`pipelines/sec_ingestion.py`), polls Atom feed every 30s, dedup, risk-signal extraction
- [x] Sprint 4 — Synthetic CRM & support event generator (`pipelines/synthetic_crm.py`), 47 parametrised tests
- [x] Sprint 5 — Week 1 wrap-up: stub files for graph, scoring, dashboard, baseline_rag packages
- [x] Sprint 6 — Graph write-back via Bolt (`graph/memgraph_client.py`), retry backoff, upsert_account/upsert_event, 7 integration tests
- [x] Sprint 7 — Cypher query layer + Agent Context API (`graph/context_api.py`), `get_agent_context()`, freshness labels, 4 integration tests
- [x] Sprint 8 — SEC feed URL + entry parsing fixes (CIK from title, timestamp = filing date)
- [x] Sprint 9 — OpenTelemetry instrumentation + live latency dashboard (`observability/`), cross-process IPC via `akf_latency_stats.json`, 67 tests passing
- [x] Sprint 10 — Latency measurement correctness; verified profile: parse ~0.1ms, Bolt warm 1–2ms, P50 ~15s
- [x] Sprint 11 — Tier-1 Deterministic Resolver live (`pipelines/resolver/tier1_deterministic.py`); node_key = SHA256(normalized)[:16]; 0 duplicates, 116 Account nodes, 79 tests passing
- [x] Sprint 12 — Tier 2 Graph-Contextual Resolver (`pipelines/resolver/tier2_graph_context.py`)
- [x] Sprint 13 — Tier 3 LLM-as-Judge (`pipelines/resolver/tier3_llm_judge.py`)
- [x] Sprint 14 — Ghost Node Pattern
- [x] Sprint 15 — Risk scoring layer (`scoring/account_health.py`)
- [x] Sprint 16 — Final Polish & Deployment

## Upcoming Sprints
- [ ] Sprint 17 — RAG Baseline Comparison (Pinecone + LlamaIndex)

## Risk Score Weights
| Signal | Weight |
|---|---|
| TAKEOVER_BID | 40 |
| EXECUTIVE_DEPARTURE | 30 |
| DELISTING_RISK | 25 |
| EARNINGS_MISS | 20 |
| CRITICAL_SUPPORT | 15 |
| CONTRACT_RENEWAL_AT_RISK | 10 |
| Clamp to [0, 100] | — |

## Notes (Technical Blockers / Gotchas)
- **Python env**: always use `.venv312/bin/python` (Python 3.12) — default `.venv` is 3.14 and lacks pyarrow/Pathway wheels.
- **pip freeze**: use `.venv312/bin/python -m pip freeze > requirements.txt` — NOT `python3.12 -m pip freeze` (points at system Python).
- **Memgraph auth**: `admin/admin` — default no-auth config will fail silently.
- **Schema migration rule**: changing a Memgraph MERGE key creates duplicate nodes. Always run a backfill migration before deploying a key change.
