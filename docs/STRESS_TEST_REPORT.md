# 🛡️ Autonomous Knowledge Fabric — Stress Test & Performance Report
**Date:** May 6, 2026
**Environment:** MacBook Air (M4, 10-Core, 24GB RAM)
**Graph Engine:** Omnigraph v0.4.1 (RustFS / Local S3 Backend)

## 1. Executive Summary
This document summarizes the findings from an 8-hour continuous hydration stress test of the SEC EDGAR ingestion pipeline into the Omnigraph S3-native Knowledge Fabric. 

The primary goals of the test were to:
1. Verify system stability and memory footprint during a prolonged continuous polling phase.
2. Measure and mitigate the S3 Manifest Commit Penalty for real-time ingestion.
3. Decouple "Fast-Path" deterministic entity resolution from "Slow-Path" LLM-based corroboration to ensure high throughput while maintaining graph integrity.

**Final 8-Hour Hydration Scale:**
*   **Total Accounts:** 116 (Deduplicated successfully via Tier-1 Resolver)
*   **Total Events:** 674 (SEC 8-K filings)
*   **Graph Connections:** 672
*   **Weak-Signal Fragments:** 194 (Quarantined in isolated Omnigraph side-branches)

---

## 2. Ingestion Throughput: Atomic vs. Batched Commits

### The S3 Manifest Penalty (Atomic Commits)
Omnigraph's S3-native architecture provides high-durability and zero-downtime time-travel reads by making data immutable (similar to Apache Iceberg/Delta Lake). However, this means every write requires a new S3 Manifest file to be committed. 

During initial testing, the `OmnigraphSink` executed **Atomic Commits**—passing `sync_branch=true` on every single incoming event.
*   **Observed Latency (Atomic):** `~83.6 seconds` per event.
*   **Impact:** The pipeline ground to a halt. The CPU usage on the host machine spiked to ~90% as the Dockerized RustFS layer and Omnigraph Server struggled with constant, small I/O metadata operations.

### The Mitigation (Batched Commits)
To achieve real-time streaming throughput on an S3-native graph, we moved to **Batched Commits** using an in-memory application buffer (`OmnigraphSink`).
*   **Strategy:** Events are buffered in memory up to `batch_size=100` (or until `flush_interval_secs=3.0` elapses).
*   **Implementation:** During the flush loop, individual events are sent to the server asynchronously. The crucial optimization was setting `sync_branch=False` for the first 99 events, and only forcing `sync_branch=True` on the 100th event.
*   **Observed Latency (Batched):** Reduced the S3 penalty from ~83s to **~53ms per event**. 
*   **Result:** The pipeline effortlessly kept pace with the live SEC RSS feed without accumulating memory lag. Throughput stabilized at roughly `0.027 events/sec` (dictated by the feed's actual publication rate, not system bottleneck).

---

## 3. Dashboard Read Performance: Branch Head vs. Pinned Snapshots

### The Metadata Check Penalty
By default, querying a branch (e.g., `main`) in Omnigraph requires the server to make a synchronous `S3 Head` network call to verify if a newer Manifest file has been written since the last query.
*   **Observed Latency (Branch Head):** `~840ms` per dashboard refresh.
*   **Impact:** Streamlit's reactive execution model meant the dashboard felt sluggish, pulling high CPU load simply to check for new data on every keystroke.

### The Mitigation (Pinned Snapshot Reads - "The Fast Path")
To achieve sub-millisecond retrieval latency for the Dashboard and Agent RAG context, we implemented **Pinned Snapshot Reads**.
*   **Strategy:** Upon initialization, the Streamlit app queries the `/commits` API to grab the `latest_snapshot_id`.
*   **Implementation:** This `snapshot_id` is cached and explicitly passed in the JSON payload of every `read` query, bypassing the S3 metadata network check entirely because the underlying Lance data fragments are immutable and memory-mapped.
*   **Result:** Read operations dropped to **< 1ms**. The dashboard became instantly responsive. We added a "Sync to Head" UI control to allow users to manually update their pinned view when necessary.

---

## 4. Entity Resolution & Side-Branch Strategy

### Tier-1 (Deterministic / Fast-Path)
Events with strong identifiers (e.g., CIK numbers parsed from the SEC Atom feed) were routed directly into the `main` branch buffer. The deduplication logic successfully consolidated 674 events into just 116 canonical Accounts.

### Tier-3 (LLM Judge / Slow-Path)
Events lacking strong identifiers ("Weak Signals") were isolated into unique Omnigraph side-branches (e.g., `fragment-00ddb3b8`) to prevent corrupting the `main` graph with duplicate or orphaned nodes.
*   **Observation:** The 8-hour run produced 194 unverified side-branches.
*   **The Batch Resolver:** A decoupled script (`pipelines/batch_resolver.py`) was built to process these fragments asynchronously using a Gemini 2.5 Flash LLM.
*   **Rate Limit Bottleneck:** The resolver initially failed because it exceeded the Gemini Free Tier limit of 15 Requests Per Minute (RPM). It triggered `429 RESOURCE_EXHAUSTED` exceptions from the `instructor` library.
*   **Mitigation:** We implemented a robust backoff strategy:
    1. A base throttle of `time.sleep(5)` ensures a maximum of 12 RPM.
    2. Proper exception propagation allows the outer loop to catch `429` errors and initiate a `time.sleep(60)` cooldown before retrying.

## 5. Conclusion
The 8-hour stress test proved that the pathway-to-omnigraph architecture is highly viable for real-time intel generation, provided the following rules are strictly observed:
1. **Never sync on every write:** S3-native graphs *must* use batched ingestion.
2. **Never poll the head for UI/RAG:** Always pin your session to a snapshot ID for reads.
3. **Decouple LLM Evaluation:** Asynchronous batch resolution on side-branches protects the ingestion pipeline from third-party API rate limits and latency.
