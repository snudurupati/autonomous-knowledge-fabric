# 🚀 Autonomous Knowledge Fabric: Omnigraph Pivot
### S3-Native Account Intelligence Reference Architecture

> *"Most enterprise AI agents are failing in production because they rely on stale context — we're feeding 2026-speed models with 1996-speed batch pipelines."*

**stream-graph-rag** is a 90-day, build-in-public project that solves the **"Missing Middle"** of the enterprise AI stack: the gap between high-velocity business events and the context your agents actually reason over.

This branch (`architecture/omnigraph-pivot`) represents a fundamental architectural fork. We are migrating from a "Hot State" in-memory graph (Memgraph) to an "Immutable Snapshot" S3-native graph (Omnigraph) to leverage Git-flow for data and MVCC branching for entity resolution.

---

## 📖 The Problem: Context Debt

Batch-based RAG creates a **"Context Debt"** — a growing gap between what your agent *believes* and what is *actually true*. 

**The QBR Scenario:**
A Sales Director walks into a Quarterly Business Review with "Global Corp." Their RAG agent says the account is *"Stable."* In reality, 20 minutes ago:
* An SEC filing hit the wire showing a hostile takeover bid.
* A support ticket was just escalated to "Critical" for their main subsidiary.

Traditional RAG misses this. **stream-graph-rag** flags it in under 60 seconds.

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

### The Architectural Shift

| Feature | Memgraph + Pathway (Baseline) | Omnigraph (New Pivot) |
| :--- | :--- | :--- |
| **State Storage** | In-Memory (Volatile/Snapshot) | S3-Native (Immutable/Versioned) |
| **Concurrency** | ACID / Lock-based | MVCC / Branch-based |
| **Buffering** | Custom In-Memory (`GhostNodeManager`) | Native Headless Branches |
| **Recovery** | WAL / Replay | Instant (Snapshot Pinned) |

---

## ⚙️ Installation & Local Infrastructure

To accurately benchmark S3 commit latencies against the sub-2ms Memgraph baseline, this project utilizes a local RustFS S3 simulator. 

**Critical Requirement:** You must isolate the Omnigraph dependencies from the Memgraph baseline to avoid environment corruption.

### 1. Core Binaries & CLI Dependencies
macOS PEP-668 protections will block the Omnigraph bootstrap script if it attempts to install system-level packages via `pip`. Install the required CLI tools globally via Homebrew first:

```bash
brew tap ModernRelay/tap
brew install ModernRelay/tap/omnigraph
brew install awscli
```

### 2. Local RustFS Bootstrap
Ensure Docker is running, then execute the one-command bootstrap. This bypasses AWS network latency by creating a local S3-compatible backend.

```bash
curl -fsSL [https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh](https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh) | bash
```
* **RustFS (S3 Endpoint):** `127.0.0.1:9000`
* **Omnigraph Server:** `127.0.0.1:8080`

### 3. Isolated Python Environment
Do not run the new architecture in your legacy Memgraph environment. 

```bash
# Create and activate a dedicated environment
python -m venv .venv-omnigraph
source .venv-omnigraph/bin/activate

# Install S3 and stream processing dependencies
pip install pathway streamlit boto3 requests
```

---

## 🗓️ Sprint 17: The Omnigraph Ingestion Sink

**Goal:** Deprecate the in-memory `GhostNodeManager` logic.

When a new, unverified entity hits the pipeline, the `OmnigraphSink` dynamically creates a headless side-branch via the Omnigraph REST API. 
* If the 3-Tier Resolver generates an evidence score > 70, the side-branch is fast-forward merged into `main`.
* If the threshold is missed, the branch is dropped, ensuring zero graph pollution.
