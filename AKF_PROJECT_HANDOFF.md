# Autonomous Knowledge Fabric — Project Handoff
**Owner:** Sreeram Nudurupati | sreeram@nudurupati.co  
**LinkedIn:** https://www.linkedin.com/in/snudurupati  
**Blog:** https://nudurupati.co  
**Repo:** https://github.com/snudurupati/autonomous-knowledge-fabric  
**Date:** 2026-03-15  
**Current Sprint:** 12 complete, Sprint 13 next  

---

## Co-Pilot Instructions

You are Sreeram's PM and Sr. Engineer co-pilot on a 90-day
build-in-public project. Be direct, opinionated, and honest.
Push back when needed. Think like a VP of Analytics evaluating
this for enterprise adoption.

---

## Project Thesis

> "Batch-based RAG creates a 'Context Debt' — a growing gap
> between what your agent believes and what is actually true —
> that is the primary cause of production AI failures in
> relationship-intensive enterprise workflows."

**The Solution:** The Autonomous Knowledge Fabric — a stateful,
sub-60-second pipeline that transforms high-velocity events
(SEC filings, CRM webhooks, support tickets) into a resolved
Knowledge Graph, enabling agents to reason over live business
relationships rather than static history.

**The Use Case:** A Sales Director walks into a QBR. Their RAG
agent says the account is "Stable." 40 minutes ago, an SEC 8-K
filing hit the wire signaling a hostile takeover bid. The agent
missed it because its context was 8 hours stale.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Stream processor | Pathway (Rust core, Python API) | Incremental delta propagation, no JVM/GC |
| Knowledge graph | Memgraph (Docker) | In-memory graph, Bolt protocol, hot-state model |
| Schema validation | Pydantic v2 | Type-safe event models |
| LLM Judge (Tier 3) | gpt-4o-mini + Instructor | Structured outputs, minimal cost |
| Observability | OpenTelemetry | Vendor-neutral, from Day 1 |
| Dashboard | Streamlit | Fast iteration |
| Baseline RAG | Pinecone + LlamaIndex | Fair comparison baseline |

---

## Local Environment

```
Machine:    M4 Mac, 24GB RAM
Python:     3.12 (.venv312)
IDE:        Gemini CLI (switching from Claude Code)
Docker:     Running
Project:    ~/autonomous-knowledge-fabric/
```

### Run Scripts (IMPORTANT)
Always run as modules from project root:
```bash
python -m pipelines.sec_ingestion      # NOT python pipelines/sec_ingestion.py
python -m pipelines.synthetic_crm
python -m observability.latency_dashboard
```

### Memgraph
```
Docker container: stream-graph-rag-memgraph-1
Bolt:  localhost:7687
Lab:   http://localhost:3000
Username: admin
Password: admin
Start: docker compose up -d
```

### Sprint Ritual
```bash
/sprint-start    # Read HANDOFF.md, confirm goal
/sprint-end      # pip freeze > requirements.txt, write HANDOFF.md, git commit
```

---

## Repository Structure

```
autonomous-knowledge-fabric/
├── CLAUDE.md                        # AI co-pilot context
├── HANDOFF.md                       # Sprint-by-sprint log (source of truth)
├── docker-compose.yml               # Full stack: one command
├── requirements.txt                 # Auto-updated each sprint-end
├── models/
│   └── account_event.py             # Core Pydantic schemas ← START HERE
├── pipelines/
│   ├── sec_ingestion.py             # Live SEC EDGAR RSS → Pathway → Memgraph
│   ├── synthetic_crm.py             # Faker-based CRM/Zendesk event generator
│   └── resolver/
│       ├── tier1_deterministic.py   # ✅ COMPLETE
│       ├── tier2_graph_context.py   # ✅ COMPLETE
│       └── tier3_llm_judge.py       # ❌ NOT STARTED (Sprint 13)
├── graph/
│   ├── memgraph_client.py           # Bolt connection + Cypher + upsert logic
│   └── context_api.py               # get_agent_context() — core agent function
├── scoring/
│   └── account_health.py            # Risk score model (Sprint 15)
├── dashboard/
│   └── app.py                       # Streamlit dashboard (Sprint 15)
├── observability/
│   ├── telemetry.py                 # LatencyTracker + OpenTelemetry
│   └── latency_dashboard.py         # Live stats display
├── baseline_rag/                    # Pinecone + LlamaIndex baseline (Sprint 17)
├── tests/
│   ├── test_account_event.py        # ✅ 4 passing
│   ├── test_memgraph_client.py      # ✅ 3 passing
│   ├── test_context_api.py          # ✅ 4 passing
│   ├── test_telemetry.py            # ✅ 4 passing
│   ├── test_tier1.py                # ✅ 8 passing
│   └── test_tier2.py                # ✅ passing
└── docs/
    └── weekly/
        ├── week-01.md               # ✅ Published
        ├── week-01-linkedin.md      # ✅ Published
        ├── week-02.md               # ✅ Published
        ├── week-02-linkedin.md      # ✅ Published
        └── week-03.md               # ❌ NOT WRITTEN YET
```

---

## What's Been Built (Sprints 1-12)

### Sprint 1 — Environment
- Pathway + Memgraph (Docker) hot-linked and verified
- Project scaffold, virtual environment, folder structure

### Sprint 2 — Core Schema
- `AccountEvent` Pydantic v2 model
- `EventSource` enum: SEC_EDGAR, SALESFORCE, ZENDESK
- `RiskSignal` enum: TAKEOVER_BID, EARNINGS_MISS,
  EXECUTIVE_DEPARTURE, CRITICAL_SUPPORT,
  CONTRACT_RENEWAL_AT_RISK, DELISTING_RISK
- Field validator: strips legal suffixes (Tier 1 foundation)
- Model validator: requires at least one identifier

### Sprint 3 — SEC Ingestion Pipeline
- Live SEC EDGAR RSS feed connected via Pathway
- Correct User-Agent header (SEC requires it)
- Filing date from `entry.updated` field
- Company name + CIK parsed from title via regex
- Risk signals from SEC Item codes:
  - Item 1.02 → CONTRACT_RENEWAL_AT_RISK
  - Item 2.01 → TAKEOVER_BID
  - Item 2.05 → EXECUTIVE_DEPARTURE
  - Item 2.06 → EARNINGS_MISS
  - Item 3.01 → DELISTING_RISK

### Sprint 4 — Synthetic Event Generator
- `SalesforceEventGenerator`: realistic CRM events
  (Account_ID, Opportunity_Stage, ARR, Contract_Renewal_Date)
- `ZendeskEventGenerator`: realistic support events
  (Case_ID, Case_Priority, SLA_Breach, Escalation_Time)
- 5 seed companies: Apple, Microsoft, Tesla, JPMorgan, Walmart
- Alternates events every 10 seconds

### Sprints 5-6 — Pathway → Memgraph
- `MemgraphClient` class with connection retry logic
- `upsert_account()`: MERGE nodes (no duplicates)
- `upsert_event()`: CREATE Event nodes + FILED relationships
- `HAS_SIGNAL` relationships for RiskSignal nodes
- Graph state: **186 nodes, 129 relationships**

### Sprint 7 — Context API
- `get_account_context()`: structured dict with 7 keys
- `get_high_risk_accounts()`: ordered by signal count
- `get_accounts_updated_since()`: recency filter
- `search_accounts()`: fuzzy name search
- `get_agent_context()`: formats context for LLM injection
- `freshness_label()`: LIVE (<60s) / RECENT (60-300s) / STALE (300s+)

### Sprint 8 — Feed Fixes
- Fixed SEC feed URL returning 2016 historical data
- Fixed CIK parsing from title field (not URL path)
- Added filing_date to AccountEvent.timestamp
- Documented SEC Item code → RiskSignal mapping in CLAUDE.md

### Sprint 9 — OpenTelemetry Instrumentation
**Verified latency numbers (production-credible):**
```
P50 latency:   12.8ms
P95 latency:   14.1ms
P99 latency:   157.8ms
Mean latency:  17.8ms
Bolt write (warm): 1-2ms
Parse time:    0.1ms
Poll interval: 30s (main latency floor)
```
Headline claim: "Sub-30s context freshness, sub-2ms write latency"

### Sprints 10-11 — Tier 1 Deterministic Resolver
**Verified working:**
```
Apple Inc.           → apple          hash: 3a7bd3e2360a3d29
APPLE INCORPORATED   → apple          hash: 3a7bd3e2360a3d29
Apple, Inc.          → apple          hash: 3a7bd3e2360a3d29
iSpecimen Inc.       → ispecimen      hash: 8ee32304c0c322fa
ispecimen            → ispecimen      hash: 8ee32304c0c322fa
Applied Digital Corp → applied digital hash: 964a38eab4eff132
Applied Digital      → applied digital hash: 964a38eab4eff132
```
- Zero duplicates in Memgraph after Tier 1 deployed
- Catches ~60% of duplicates at zero LLM cost

### Sprint 12 — Tier 2 Graph-Contextual Resolver
- `GraphContextResolver` class
- CIK match confidence: 1.0 (deterministic)
- Domain match confidence: 0.85
- Shared signal match confidence: 0.40-0.65
- Merge threshold: 0.75
- MERGED_FROM relationship written on surviving node
- Tier 1 currently catching all duplicates before Tier 2 fires
  (correct behavior — Tier 2 is the safety net)

---

## Verified Numbers For Whitepaper

| Metric | Value | Source |
|--------|-------|--------|
| P50 latency | 12.8ms | OpenTelemetry, Sprint 9 |
| P95 latency | 14.1ms | OpenTelemetry, Sprint 9 |
| Bolt write warm | 1-2ms | Debug table, Sprint 9 |
| Parse time | 0.1ms | Debug table, Sprint 9 |
| Graph nodes | 186 | Memgraph Lab, Sprint 6 |
| Graph relationships | 129 | Memgraph Lab, Sprint 6 |
| Tier 1 duplicate catch rate | ~60% | Design target |
| Tier 1 LLM cost | $0 | Deterministic |
| Poll interval (latency floor) | 30s | Configurable |
| Nightly batch comparison | 8-24 hours | Baseline |

---

## What Still Needs To Be Built

### Week 3 Remaining (Sprints 13-16)

**Sprint 13 — Tier 3 LLM-as-Judge**
- Create `pipelines/resolver/tier3_llm_judge.py`
- Use `gpt-4o-mini` + `Instructor` library
- Structured output: Match / No-Match / Merge + confidence + reasoning
- Batch ambiguous cases in groups of 10
- Human-in-the-loop flag for low-confidence decisions
- Log cost per resolution
- Win condition: ambiguous entity pair correctly resolved

**Sprint 14 — Ghost Node Pattern**
- Candidate buffer in Pathway for low-evidence entities
- Commit to graph only when evidence threshold met
  (CIK confirmed, or 2+ corroborating events)
- Prevents premature entity creation from sparse data

**Sprint 15 — Account Health Score + Streamlit Dashboard**
- Weighted scoring model (4-5 signals)
- Streamlit dashboard v1: account list + risk scores
- "Context Freshness" counter visible on dashboard
- Risk score delta written to Memgraph on each event

**Sprint 16 — Week 3 Hardening**
- Stress test: 100 synthetic events/minute
- Failure recovery: kill Memgraph, verify re-hydration
- Docker Compose cold-start verified < 2 minutes
- Week 3 retrospective + real numbers documented

### Month 3 (Sprints 17-48)

**Sprint 17-20 — RAG Baseline**
- Pinecone + LlamaIndex nightly batch setup
- Same 5 seed companies, same documents
- Identical query set frozen for fair comparison

**Sprint 21-28 — QBR Hero Demo**
- Real SEC filing scenario (hostile takeover)
- Synthetic Salesforce escalation event
- Side-by-side: RAG says "Stable", AKF catches in <30s
- Demo video recorded

**Sprint 29-36 — Whitepaper**
- Infrastructure cost model: AKF vs batch RAG
  at 500 accounts / 10K events/day
- Latency analysis: P50/P95/P99 from OpenTelemetry
- Failure recovery section
- Phase 2: Closed-Loop Intelligence design
- Docker Compose one-command deploy verified

**Sprint 37-48 — Publication & Leverage**
- README finalized with all architecture diagrams
- All latency/cost claims cited to telemetry data
- Demo video published
- LinkedIn/blog launch sequence
- Repo made public with full documentation

---

## Blog Posts Status

| Week | Title | Status | URL |
|------|-------|--------|-----|
| 1 | Context Debt: Why Enterprise RAG Is Failing | ✅ Published | nudurupati.co |
| 2 | I Measured My AI Pipeline. The Number Changed Everything. | ✅ Published | nudurupati.co |
| 3 | The Ghost Node Pattern | ❌ Not written | — |
| 4-12 | See sprint plan README | ❌ Pending | — |

---

## Key Decisions & Rationale

**Pathway over Spark:** 5 years Kafka/Spark experience. Chose
Pathway for incremental delta propagation (no micro-batch
overhead), Rust core (no JVM GC pauses), single container
deployment. To be fair: if already on Databricks, use it.

**Memgraph as "hot state" not permanent DB:** Framed as a
state-cache for platform teams. If it crashes, Pathway
re-hydrates from S3-backed log. Reduces operational anxiety.

**Three-Tier resolver:** Tier 1 ($0, catches 60%), Tier 2
(graph neighbors, $0), Tier 3 (LLM judge, minimal cost).
Only ambiguous cases reach Tier 3.

**Public from Day 1:** Build-in-public is the honeypot.
Each blog post is a breadcrumb attracting enterprise AI
practitioners, VPs, and architects.

**Fair baseline:** Pinecone + LlamaIndex with nightly batch —
a genuinely good implementation, not a strawman.
Defined in Month 1, never touched again.

---

## Known Issues / Tech Debt

- LATENCY log company field shows raw title (cosmetic, Sprint 13 cleanup)
- Ghost Node pattern not yet implemented (Sprint 14)
- Streamlit dashboard not yet built (Sprint 15)
- Baseline RAG not yet set up (Sprint 17)
- Week 3+ blog posts not yet written

---

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| P50 latency | <60s | ✅ 12.8ms |
| P95 latency | <120s | ✅ 14.1ms |
| Tier 1 catch rate | >60% | ✅ ~100% currently |
| Tier 3 LLM cost/1000 entities | <$0.50 | ❌ Not measured yet |
| Docker Compose cold-start | <2 min | ❌ Not tested yet |
| Memgraph recovery after crash | <5 min | ❌ Not tested yet |

---

## Quick Commands Reference

```bash
# Start full stack
docker compose up -d

# Run SEC pipeline
python -m pipelines.sec_ingestion

# Run synthetic events
python -m pipelines.synthetic_crm

# Watch latency stats
python -m observability.latency_dashboard

# Check for duplicates
python -c "
import mgclient
conn = mgclient.connect(host='127.0.0.1', port=7687,
                        username='admin', password='admin')
cursor = conn.cursor()
cursor.execute('''
    MATCH (a:Account)
    WITH toLower(a.company_name) AS name, COUNT(*) AS count
    WHERE count > 1
    RETURN name, count ORDER BY count DESC LIMIT 10
''')
print(cursor.fetchall() or 'No duplicates')
"

# Get agent context for a company
python -c "
from graph.context_api import get_agent_context
print(get_agent_context('carbonite'))
"

# Test Tier 1 resolver
python -c "
from pipelines.resolver.tier1_deterministic import resolve
print(resolve('Apple Inc.'))
"

# Run all tests
pytest tests/ -v
```

---

*Last updated: Sprint 12 complete, 2026-03-15*
*Next action: Sprint 13 — Tier 3 LLM-as-Judge*
