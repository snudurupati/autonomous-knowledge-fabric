# Autonomous Knowledge Fabric - Architectural Conventions

## Omnigraph S3-Native Storage & Latency Mechanisms

Omnigraph operates on an immutable, append-only S3-native architecture built on top of Lance format (similar to Apache Iceberg or Delta Lake). Understanding the distinction between reads is critical for meeting the sub-60s agent context assembly SLA.

### 1. Pinned Snapshot Reads (The Fast Path: < 1ms)
**When to use:** For Agent Context / RAG retrieval.
**Mechanism:** Pinned snapshot reads are equivalent to Lance's "Time Travel Queries" targeting a specific, immutable Manifest version.
**Performance:** Because the Manifest and its underlying data fragments are immutable, providing a `snapshot_id` bypasses the S3 metadata network check completely. The Omnigraph server maps the query instantly to locally cached, memory-mapped fragments.
**API Requirement (v0.4.1+):** You MUST provide both the `branch` and `snapshot` parameters in the payload. Omitting the branch causes the query router to fall back to an unoptimized path.

### 2. Branch Head Reads (The Slow Path: ~840ms)
**When to use:** When you specifically need the absolute latest state and cannot tolerate a slightly stale pinned snapshot.
**Mechanism:** Querying a branch without a snapshot targets the "Latest Version" (head). 
**Performance:** The server MUST make a synchronous network call to S3 (e.g., `S3 Head`) to verify if a newer Manifest file exists before executing the query. This network metadata check incurs a severe latency penalty.

### 3. Write Path / S3 Commit Penalty
**When to use:** Data Ingestion
**Mechanism:** Every commit generates new Manifests and data fragments in S3.
**Performance (v0.4.1+):** Single-row mutations incur a ~3.3s commit penalty. Production systems must **batch ingestions** (which achieve ~53ms/event) or use transactional GQL blocks (`ingest_event_complete.gq`) to minimize commit volume.
