# 🚀 Autonomous Knowledge Fabric
### S3-Native Account Intelligence Reference Architecture

> *"Most enterprise AI agents are failing in production because they rely on stale context — we're feeding 2026-speed models with 1996-speed batch pipelines."*

**autonomous-context-fabric** (formerly *stream-graph-rag*) is a 90-day, build-in-public project that solves the **"Missing Middle"** of the enterprise AI stack: the gap between high-velocity business events and the context your agents actually reason over.

Built with **Pathway** (stateful stream processing) + **Omnigraph** (S3-native immutable graph) to deliver sub-60-second account intelligence — directly from SEC filings, CRM webhooks, and support events.

---

## 📖 The Problem: Context Debt

Batch-based RAG creates a **"Context Debt"** — a growing gap between what your agent *believes* and what is *actually true* — that is the primary cause of production AI failures in relationship-intensive enterprise workflows.

**The QBR Scenario:**
A Sales Director walks into a Quarterly Business Review with "Global Corp." Their RAG agent says the account is *"Stable."* In reality, 20 minutes ago:
- An SEC filing hit the wire showing a hostile takeover bid
- A support ticket was just escalated to "Critical" for their main subsidiary

Traditional RAG misses this. **Autonomous Knowledge Fabric** flags it in under 60 seconds.

---

## 🧠 Key Findings & Lessons Learned (Omnigraph Pivot)

During our migration sprint from Memgraph to an S3-native architecture, we uncovered several critical insights:

1. **The Agent-Native Paradigm**: Omnigraph is designed for AI agents. By arming the Gemini CLI with `omnigraph-best-practices` and `omnigraph-intel-bootstrap` skills, the agent successfully synthesized the schema, queries, and custom HTTP clients from scratch without existing SDK examples.
2. **Latency & Real-Time Viability**: S3-native architecture changes the performance profile. 
   * **Reads (~80ms)**: Highly performant and easily supports our sub-60s agent context assembly SLA.
   * **Writes (~1.2s)**: Single-row upserts incur a file-creation penalty due to S3 commits. While usable for background processing, high-throughput systems *must* batch ingestions.
3. **Developer Experience**: Local S3 simulators (like RustFS) require explicit dummy credentials to bypass AWS metadata service (IMDS) timeouts.

---

## 🏗️ Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     Event Sources                           │
│   SEC EDGAR RSS    Synthetic CRM    Synthetic Zendesk       │
└──────────┬──────────────┬─────────────────┬────────────────┘
           │              │                 │
           ▼              ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│              Pathway Stream Processor (Single Container)    │
│   ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│   │ Normalization│  │  3-Tier      │  │  Omnigraph Sink │   │
│   │ & Extraction │─▶│  Resolver    │─▶│  (S3/Boto3)     │   │
│   └──────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Omnigraph (S3-Native / MVCC)                   │
│                                                             │
│   [Headless Branch: fragment/f1b20889]  <-- Unverified      │
│        │                                    Entity Buffer   │
│        └──(Threshold Met)──▶ Fast-Forward Merge             │
│                                 │                           │
│   [Main Branch] ────────────────┴───────▶ Pinned Snapshot   │
└─────────────────────────────────────────────────┬───────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────┐
│         Account Intelligence Agent + Streamlit Dashboard    │
│                                                             │
│   Account: Global Corp    Risk Score: 🔴 CRITICAL           │
│   Context Freshness: 14 seconds ago    ████████░░ 82/100    │
└─────────────────────────────────────────────────────────────┘
```

### The Three-Tier Entity Resolver (Core IP)

| Tier | Method | Catches | LLM Cost |
|------|--------|---------|----------|
| **Tier 1** | Deterministic hashing (normalize, trim, regex) | ~60% of duplicates | $0 |
| **Tier 2** | Graph-contextual neighbor matching in Omnigraph | ~30% of remaining | $0 |
| **Tier 3** | LLM-as-Judge via `gpt-4o-mini` + Instructor | Final ~10% ambiguous cases | Minimal |

---

## ⚙️ Quick Start: Omnigraph Infrastructure

This project uses a local RustFS S3 simulator to benchmark commit latencies.

### 1. Environment & S3 Credentials
Create an externalized `.env.omni` file to bypass IMDS timeouts.

```bash
cat <<EOF > .env.omni
AWS_ACCESS_KEY_ID=rustfsadmin
AWS_SECRET_ACCESS_KEY=rustfsadmin
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://127.0.0.1:9000
AWS_ENDPOINT_URL_S3=http://127.0.0.1:9000
AWS_ALLOW_HTTP=true
AWS_S3_FORCE_PATH_STYLE=true
EOF
```

### 2. Local RustFS & Binaries
```bash
# Installs binaries to ./.omnigraph-rustfs-demo/bin and starts RustFS (Port 9000)
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh | bash
```

### 3. Initialize & Start Server
```bash
export $(cat .env.omni | xargs)
./.omnigraph-rustfs-demo/bin/omnigraph init --schema schema.pg s3://omnigraph-local/crm-fixed
./.omnigraph-rustfs-demo/bin/omnigraph-server --bind 127.0.0.1:8080 s3://omnigraph-local/crm-fixed
```

---

## 🗓️ 90-Day Sprint Roadmap

### MONTH 1 — "The Pulse" Foundation (Pivot to S3-Native)
**Goal: Prove the live view works. An observer sees a news item hit the wire and the graph updates its risk score in <60 seconds.**

| Week | Sprint | Deliverable |
|------|--------|-------------|
| **W1** | 1-4 | Repo setup. Omnigraph + RustFS initialized. `AccountEvent` schema for SEC filings. |
| **W2** | 5-8 | S3-native sink via Boto3. `upsert_account` and `upsert_event` logic. Context API. |
| **W3** | 9-12 | OpenTelemetry instrumentation. Tier 1/2 Resolvers (Deterministic & Neighbor matching). |
| **W4** | 13-16 | Tier 3 Resolver (Gemini 1.5). Snapshot-pinned reads. Streamlit Dashboard v1. |

**Month 1 Deliverable:** A live dashboard showing real SEC filings, entities extracted and risk-scored within 60 seconds using S3-native snapshotting.

---

### MONTH 2 — "The Identity" Engine
**Theme: Resolution & Maturity**
**Goal: Solve the "Acme Corp" duplication problem using MVCC branching.**

*   **Week 5:** Tier 1: Deterministic normalization (strip legal suffixes, trim).
*   **Week 6:** Tier 2: Graph-contextual matching (shared domains/CIKs/executives).
*   **Week 7:** Tier 3: LLM-as-Judge using Instructor-structured prompts.
*   **Week 8:** Operational Hardening: Docker Compose v1, Salesforce/Zendesk synthetic schemas.

---

### MONTH 3 — "The CFO" Demo
**Theme: ROI & Comparison**
**Goal: Prove value-per-query and operational simplicity.**

*   **Week 9:** RAG Baseline Comparison (Nightly batch refresh vs. Real-time).
*   **Week 10:** The QBR Hero Demo: Scenario script where RAG fails and Fabric succeeds.
*   **Week 11:** The Whitepaper: Infrastructure cost model (S3-native vs. In-memory vs. Nightly RAG).
*   **Week 12:** Publication: README finalized, Whitepaper published, Demo video released.

---

## 📊 Performance Benchmarks (Sprint 20)

| Metric | Omnigraph (Rust/S3) | Memgraph (Legacy/In-Memory) |
| :--- | :--- | :--- |
| **P50 Upsert Latency** | **~1,200 ms** | ~2.00 ms |
| **P99 Upsert Latency** | **~1,800 ms** | ~5.00 ms |
| **P50 Context Read** | **~80 ms** | ~1.50 ms |

*Note: Omnigraph upserts include 3 atomic mutations (Account, Event, Link) per ingestion over S3.*

---

## 🤖 AI-Native Management

This repository is architected for AI agents. Any agent operating within this workspace **must** utilize the following specialized skills:

1.  **`omnigraph-best-practices`**: Required for all `schema.pg` evolutions and `.gq` query authoring.
2.  **`omnigraph-intel-bootstrap`**: Required for repository initialization and environment orchestration.

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Stream processor | [Pathway](https://pathway.com) | Rust core, Python-native, incremental deltas |
| Knowledge graph | [Omnigraph](https://omnigraph.dev) | S3-native, MVCC branching, Snapshot consistency |
| Schema validation | [Pydantic](https://docs.pydantic.dev) | Type-safe event models, Pathway-native |
| LLM Judge | Gemini 1.5 Flash + [Instructor](https://python.useinstructor.com) | Structured outputs, minimal cost |
| Observability | [OpenTelemetry](https://opentelemetry.io) | Vendor-neutral, from Day 1 |
| Dashboard | [Streamlit](https://streamlit.io) | Fast iteration, no frontend overhead |

---

## 🧠 Deep Dive: The Data Journey

The Autonomous Knowledge Fabric operates as a **push-based pipeline**. Data does not simply "sit" in Pathway; it is actively pushed through a multi-stage resolution and ingestion stack.

### 1. Normalization & Extraction (Tier 1)
*   **File**: `pipelines/sec_ingestion.py` (`_row_to_account_event`)
*   **Action**: Raw RSS/HTML entries are unescaped and parsed via Regex to extract Company Names, CIK numbers, and event types.
*   **Result**: A validated `AccountEvent` Pydantic model.

### 2. The Subscription Bridge
*   **File**: `pipelines/sec_ingestion.py` (`pw.io.subscribe`)
*   **Action**: Pathway's engine triggers the `_on_change` callback for every new event. This acts as the real-time bridge between the stream processor and the graph database.

### 3. Entity Resolution Routing (Tier 2 & 3)
*   **File**: `pipelines/routing.py` (`OmnigraphRoutingManager`)
*   **Action**: 
    *   **Tier 2 (Graph Context)**: Checks for "Strong Signals" (CIK, Domain, ID).
    *   **Branch-Based Buffering**: If an entity is "Weak" (name only), it is isolated in a **headless side-branch** (Fragment) in Omnigraph. This prevents "Context Pollution" on the `main` branch.
    *   **Promotion**: Once a threshold is met (via corroborated signals or **Tier 3 LLM Judge**), the branch is merged into `main`.

### 4. Atomic Ingestion (The Sink)
*   **File**: `engine/omnigraph/ingestion_sink.py` (`OmnigraphSink`)
*   **Action**: 
    *   **Risk Scoring**: Calculates the final health score for the account.
    *   **Multi-Mutation**: Executes three atomic GQL mutations (`insert_account`, `insert_event`, `link_account_event`) to ensure structural integrity.

---

## 🚀 How to Run: Orchestration Flow

To run the full Autonomous Knowledge Fabric, you need to coordinate the storage, database, and pipeline layers in sequence.

### 1. Start the Infrastructure (Storage Layer)
The fabric uses a local S3 simulator to manage the physical Parquet/Lance files.
```bash
docker compose up -d rustfs
```

### 2. Launch the Omnigraph Server (Database Layer)
The server provides the GQL/HTTP API that the pipelines use for ingestion.

**First-time Setup:**
If this is a fresh installation, you must initialize the repository first.
```bash
export $(cat .env.omni | xargs)
./.omnigraph-rustfs-demo/bin/omnigraph init --schema schema.pg s3://omnigraph-local/crm-fixed
```

**Start the Server:**
```bash
./.omnigraph-rustfs-demo/bin/omnigraph-server --bind 127.0.0.1:8080 s3://omnigraph-local/crm-fixed
```

### 3. Kick off an Ingestion Pipeline (Stream Layer)
You can choose between real SEC data or high-volume synthetic CRM events. Open a new terminal tab and ensure `PYTHONPATH` is set.

#### Option A: Real SEC EDGAR Stream
Polls live SEC filings and extracts risk signals.
```bash
export PYTHONPATH=.
python pipelines/sec_ingestion.py
```

#### Option B: Synthetic CRM Load Generator
Generates a high-velocity stream of synthetic account events using Faker.
```bash
export PYTHONPATH=.
python pipelines/synthetic_crm.py
```

### 4. Monitor the Live Dashboard (Visualization Layer)
View the accounts, risk scores, and event trails in a real-time UI.
```bash
export PYTHONPATH=.
streamlit run dashboard/app.py
```

---

## 📁 Repository Structure

```
autonomous-knowledge-fabric/
├── CLAUDE.md                    # AI co-pilot context
├── docker-compose.yml           # Full stack: one command
├── schema.pg                    # Omnigraph Schema-as-Code
├── models/
│   └── account_event.py         # Core Pydantic schemas
├── engine/
│   └── omnigraph/               # S3-native DB interaction
│       ├── client.py            # Snapshotted HTTP client
│       └── ingestion_sink.py    # Pathway → Omnigraph sink
├── pipelines/
│   ├── sec_ingestion.py         # SEC EDGAR RSS → Pathway
│   ├── synthetic_crm.py         # Faker-based CRM generator
│   └── resolver/                # 3-Tier Entity Resolution
├── scoring/
│   └── account_health.py        # Risk score model
├── dashboard/
│   └── app.py                   # Streamlit dashboard
├── baseline_rag/                # Pinecone + LlamaIndex baseline
├── observability/
│   └── telemetry.py             # OpenTelemetry setup
├── tests/                       # Pytest suite
└── docs/                        # Whitepaper and Weekly logs
```

---

## 🤝 Contributing & Feedback

This is a **build-in-public** project. Feedback, issues, and PRs welcome.

---

## 📄 License

MIT — use it, fork it, build on it.

---

*Built by [Sreeram Nudurupati](https://www.linkedin.com/in/snudurupati) — a practitioner who got tired of explaining to stakeholders why the AI was confidently wrong.*
