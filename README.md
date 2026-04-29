# 🚀 Autonomous Knowledge Fabric: Omnigraph Pivot
### S3-Native Account Intelligence Reference Architecture

> *"Most enterprise AI agents are failing in production because they rely on stale context — we're feeding 2026-speed models with 1996-speed batch pipelines."*

**stream-graph-rag** is a build-in-public project that solves the **"Missing Middle"** of the enterprise AI stack: the gap between high-velocity business events and the context your agents actually reason over.

This architecture migrating from a "Hot State" in-memory graph (Memgraph) to an "Immutable Snapshot" S3-native graph (Omnigraph) to leverage Git-flow for data and MVCC branching for entity resolution.

---

## 🏗️ Architecture Pivot: S3-Native & Branching

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
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Quick Start: Omnigraph Infrastructure

This project uses a local RustFS S3 simulator to benchmark commit latencies.

### 1. Environment & S3 Credentials
Do not commit credentials. Use an externalized `.env.omni` file (included in `.gitignore`).

```bash
# Create .env.omni with local RustFS defaults
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
Ensure Docker is running, then bootstrap the local infrastructure.

```bash
# Installs binaries to ./.omnigraph-rustfs-demo/bin and starts RustFS (Port 9000)
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh | bash
```

### 3. Initialize & Start Server
Initialize the S3-native repository using the established schema and start the HTTP server.

```bash
# Initialize the repository
export $(cat .env.omni | xargs)
./.omnigraph-rustfs-demo/bin/omnigraph init --schema schema.pg s3://omnigraph-local/crm-fixed

# Start the Omnigraph Server (Port 8080)
./.omnigraph-rustfs-demo/bin/omnigraph-server --bind 127.0.0.1:8080 s3://omnigraph-local/crm-fixed
```

---

## 🏁 Development & Testing

### 🧪 Verifying the Client
The Python client (`engine/omnigraph/client.py`) supports full-roundtrip entity resolution, high-risk account filtering, and **Snapshot-Pinned Reads** for immutable context.

```bash
export PYTHONPATH=$PYTHONPATH:.
./.venv-omnigraph/bin/python tests/test_omnigraph_client.py
```

### 📊 Performance Benchmarks (Sprint 20)
We compared the S3-native Omnigraph backend against our legacy in-memory baseline. While S3 overhead is higher, Omnigraph provides the consistency and versioning required for production-grade agent reasoning.

| Metric | Omnigraph (Rust/S3) | Memgraph (In-Memory) |
| :--- | :--- | :--- |
| **P50 Upsert Latency** | **~1,200 ms** | ~2.00 ms |
| **P99 Upsert Latency** | **~1,800 ms** | ~5.00 ms |
| **P50 Context Read** | **~80 ms** | ~1.50 ms |

*Note: Omnigraph upserts include 3 atomic mutations (Account, Event, Link) per ingestion event over the S3 protocol.*

---

## 🤖 AI-Native Management & Prerequisites

This property graph was architected specifically for AI agents—built by agents, for agents. To maintain the structural integrity and versioned history of the "Autonomous Knowledge Fabric," any agent operating within this workspace **must** utilize the following specialized skills:

### 🧠 Mandatory Agent Skills

1.  **`omnigraph-best-practices`**:
    *   **Usage**: Required for all `schema.pg` evolutions and `.gq` query authoring.
    *   **Agent Impact**: Enforces strict "Schema-as-Code" standards and `@key` constraints.

2.  **`omnigraph-intel-bootstrap`**:
    *   **Usage**: Required for repository initialization and environment orchestration.

### 🏗️ End-to-End Implementation

*   **Modernized Schema (`schema.pg`)**: Supports complex event trails via `AccountEvent` nodes and `HAS_EVENT` edges with full indexing.
*   **Specialized Query Library (`queries/`)**: Optimized `.gq` files for `get_account_context` and `get_high_risk_accounts`.
*   **Production Sink (`engine/omnigraph/ingestion_sink.py`)**: A Pathway-compatible sink that maps Pydantic models to graph nodes with real-time risk scoring.
*   **Snapshot Control**: The Python client implements `get_latest_snapshot_id()` to ensure agents always reason over a consistent, immutable slice of time.

This concludes the architectural pivot to an S3-native Knowledge Fabric. The system is now stabilized, verified, and ready for high-velocity account intelligence operations.
