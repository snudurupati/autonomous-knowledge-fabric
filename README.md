# 🚀 Autonomous Knowledge Fabric: Omnigraph Pivot
### S3-Native Account Intelligence Reference Architecture

> *"Most enterprise AI agents are failing in production because they rely on stale context — we're feeding 2026-speed models with 1996-speed batch pipelines."*

**stream-graph-rag** is a 90-day, build-in-public project that solves the **"Missing Middle"** of the enterprise AI stack: the gap between high-velocity business events and the context your agents actually reason over.

This branch (`architecture/omnigraph-pivot`) represents a fundamental architectural fork. We are migrating from a "Hot State" in-memory graph (Memgraph) to an "Immutable Snapshot" S3-native graph (Omnigraph) to leverage Git-flow for data and MVCC branching for entity resolution.

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
./.omnigraph-rustfs-demo/bin/omnigraph init --schema schema.pg s3://omnigraph-local/crm-repo

# Start the Omnigraph Server (Port 8080)
./.omnigraph-rustfs-demo/bin/omnigraph-server --config ./omnigraph.yaml
```

---

## 🏁 Development & Testing

### 🧪 Verifying the Client
The Python client (`engine/omnigraph/client.py`) is verified via a `unittest` suite that performs full-roundtrip entity resolution against the S3 backend.

```bash
export PYTHONPATH=$PYTHONPATH:.
./.venv-omnigraph/bin/python tests/test_omnigraph_client.py
```

---

## 🛠️ Session Documentation: Building the CRM Architecture

In this session, we built the foundational CRM architecture for Omnigraph from scratch, leveraging specialized Agent Skills.

### 🧠 Agent Skills Utilized

1.  **`omnigraph-best-practices`**:
    *   **Usage**: Guided the authoring of `schema.pg` and `.gq` query files. 
    *   **Impact**: Ensured correct use of `@key` constraints for deterministic entity resolution and identified the mandatory `rows` key in HTTP API responses.
    *   **Configuration**: Directed the migration of plaintext credentials to `.env.omni` via the `auth: env_file` directive.

2.  **`omnigraph-intel-bootstrap`**:
    *   **Usage**: Provided the operational blueprint for initializing the repository and managing local RustFS environment variables.
    *   **Impact**: Enabled seamless, one-command initialization of the S3-native graph.

### 🏗️ Implementation Details

*   **Schema (`schema.pg`)**: Versioned, S3-native entity definitions.
*   **Queries (`queries/`)**: Parameterized, type-checked GQ files.
*   **Python Client (`engine/omnigraph/client.py`)**: High-performance REST wrapper for Omnigraph `read` and `change` operations.
