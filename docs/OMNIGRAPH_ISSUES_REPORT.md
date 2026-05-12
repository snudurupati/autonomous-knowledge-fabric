# ISSUE REPORT: [BACKEND] Branch Manifest Version Drift (Phantom Table Versions)

## Status
**Open** | Priority: Critical | Type: Backend / Concurrency

## Description
A specific type of corruption occurs when side-branches are used heavily. The repository's **Root Manifest** (which tracks the state of the entire branch) becomes desynchronized from the individual **Table Manifests** (which track Account, AccountEvent, etc.). This leads to a persistent "Stale View" deadlock that survives server restarts.

### Symptoms & Error Messages
Even with a single writer and `sync_branch=true` enabled, operations fail with:
```text
stale view of 'node:Account': expected manifest table version 724 but current is 726 — refresh and retry
```
Crucially, the `omnigraph snapshot` tool (the "Root View") reports version **724**, while the error message from the storage engine (the "Table View") claims the version is actually **726**.

### Root Cause Analysis (RCA): The "Phantom Table Version"
1.  **Partial Transaction Success**: During a commit to a side-branch, Omnigraph must update multiple tables. Due to the lack of a cross-table atomic "Write-Ahead Log" in the current storage version, it is possible for a **Table Manifest** to be successfully written to S3 while the **Root Manifest Update** fails (e.g., due to a socket timeout or emulator lag).
2.  **The Drift**: The table now physically exists at Version 726 on disk/S3. However, the branch's "Table of Contents" (the Root Manifest) still thinks that table is at Version 724.
3.  **The Deadlock**: 
    *   Any new write request checks the Root Manifest and says "I'm starting from 724, the next version should be 725." 
    *   The Lance storage engine checks the physical files, sees 726 already exists, and throws a `409 Conflict`.
    *   Since the Root Manifest never "saw" 725 or 726, it can never advance itself to match the physical reality.

### Why this happens on MinIO
While MinIO solved the "False 404" issues of RustFS, it cannot fix the **logical atomicity gap** in the Omnigraph backend. If a Python process (the Ingestion or Resolver) terminates or times out during the multi-file commit handshake, the "Phantom Version" is created regardless of how robust the S3 provider is.

## Workaround / Mitigation
1.  **Metadata Pruning**: Use `omnigraph cleanup --keep 1 --confirm` to attempt to force the storage layer to align with the current root manifest. (Effectiveness: ~30%)
2.  **Rescue & Rebuild**: Perform the **Full Wipe & Reload** procedure (Step 1-7 in the previous report). This is the only 100% reliable fix once drift has occurred.

---

# ISSUE REPORT: [ARCHITECTURAL] Lack of Atomic Transactions (Dangling Manifest Corruption)

## Status
**Open** | Priority: Critical | Type: Backend / Storage Architecture

## Description
Omnigraph's underlying storage mechanism (built on Lance) lacks true atomic transactions across manifest files and branch pointers. When the system is under load, or if a client process crashes mid-operation, the repository is frequently left in an unrecoverable, corrupted state.

### Symptoms & Error Messages
Operations like `branch merge` or `change` fail persistently with "stale view" or "expected manifest version" errors, even after restarting the server or eliminating all other concurrent writers.

**Exact Error Message:**
```json
{"error":"stale view of 'edge:HAS_EVENT': expected manifest table version 239 but current is 240 — refresh and retry","code":"conflict","manifest_conflict":{"table_key":"edge:HAS_EVENT","expected":239,"actual":240}}
```

### Root Cause Analysis (RCA)
1. **Non-Atomic Commits**: During a write operation (e.g., a merge), the server writes a new manifest file (e.g., `240.manifest`) to the storage layer.
2. **The Race Condition / Crash**: Before the server can successfully update the branch's transaction pointer to reference this new manifest, the client process crashes, times out, or the S3 emulator drops the connection.
3. **The Dangling Manifest**: The storage layer now physically contains version `240`, but the branch pointer remains at `239`.
4. **Unrecoverable Deadlock**: Any subsequent attempt to write to the graph calculates the next expected version as `240`. The server attempts to write `240.manifest`, but the storage layer rejects it because the file already exists. The system is deadlocked and cannot move forward.

## Workaround
There is no programmatic API fix for this state. The only resolution is a destructive **Full Wipe & Reload** of the repository (documented below).

---

# ISSUE REPORT: [OPERATIONAL] Repository Metadata Corruption in Local RustFS (O(n) Scaling & Manifest 404s)

## Status
**Resolved (Operational Fix)** | Priority: High | Type: Reliability / Performance

## Description
Under high metadata pressure (e.g., hundreds of side-branches or frequent commits), the local RustFS emulator occasionally enters a state of "False 404s" or "Version Drift". 

### Symptoms
1.  **Read Latency Scaling**: Read performance scales linearly **O(n)** with graph size (~18ms per node floor), indicating a storage-layer bottleneck in the emulator.
2.  **Manifest Failures**: Commands like `cleanup`, `optimize`, or `schema apply` fail with `NoSuchBucket` or `Object Not Found` errors for specific `.manifest` files, even when the bucket exists.
3.  **Corruption**: The internal Lance manifest chain becomes inconsistent, preventing standard recovery operations.

## Environment
- **OS**: Darwin (macOS)
- **Omnigraph Version**: 0.4.1 (Local RustFS Bootstrap)
- **Storage**: RustFS (S3 emulator via Docker)

---

## 🛠️ Recovery Procedure: Full Wipe & Reload

If the repository becomes unresponsive or returns persistent `NoSuchBucket` errors during maintenance, follow these steps to restore stability while preserving data.

### Step 1: Export Current Data (Emergency Backup)
Attempt a full export of the graph. If it fails due to 404s, restart the RustFS container first.
```bash
# Optional: Restart container if export fails
docker restart omnigraph-rustfs-demo && sleep 5

# Export nodes and edges
export $(cat .env.omni | xargs)
./.omnigraph-rustfs-demo/bin/omnigraph export s3://omnigraph-local/crm-fixed > full_backup.jsonl
```

### Step 2: Verify Backup Integrity
Check that the node and edge counts match your expected state.
```bash
grep -c '"type":"Account"' full_backup.jsonl
grep -c '"type":"AccountEvent"' full_backup.jsonl
grep -c '"edge":"HAS_EVENT"' full_backup.jsonl
```

### Step 3: Stop the Server
```bash
kill $(pgrep omnigraph-server)
```

### Step 4: Wipe Corrupted Metadata
Delete the entire repository prefix from the local S3 bucket.
```bash
aws --endpoint-url http://127.0.0.1:9000 s3 rm --recursive s3://omnigraph-local/crm-fixed
```

### Step 5: Re-Initialize Repository
Ensure `schema.pg` is correct and contains all node and edge definitions.
```bash
./.omnigraph-rustfs-demo/bin/omnigraph init --schema schema.pg s3://omnigraph-local/crm-fixed
```

### Step 6: Reload the Data
Use `--mode overwrite` to start with a single, clean manifest version.
```bash
./.omnigraph-rustfs-demo/bin/omnigraph load --mode overwrite --data full_backup.jsonl s3://omnigraph-local/crm-fixed
```

### Step 7: Restart Server
```bash
./.omnigraph-rustfs-demo/bin/omnigraph-server --bind 127.0.0.1:8080 s3://omnigraph-local/crm-fixed
```

---

## 📈 Performance Summary (Sprint 22 Benchmarks)
| Graph Scale | P50 Pinned Read |
| :--- | :--- |
| **Tiny (1 node)** | ~450ms |
| **Small (7 nodes)** | ~550ms |
| **Full (116 nodes)** | ~2,500ms |

**Root Cause**: Local S3 emulation overhead. Production NVMe/In-Memory storage is required for sub-ms read SLAs.

---

# ISSUE REPORT: [OMNIGRAPH ENGINE] Inability to Retroactively Add Edge Constraints

## Status
**Open** | Priority: Medium | Type: Schema Evolution / Migration

## Description
Omnigraph schema migrations (v1) do not support adding constraints (e.g., `@unique(src, dst)`) to pre-existing edge types after they have been initialized in the graph.

### Symptoms & Error Messages
When running `omnigraph schema plan` after adding `@unique(src, dst)` to an existing edge, the planner rejects the migration with the following error:
```text
supported: no
- unsupported change on edge:<EdgeName>: adding constraint 'unique:dst,src' to '<EdgeName>' is not supported in schema migration v1
```

### Root Cause Analysis (RCA)
The Omnigraph 0.4.1 migration engine (`schema migration v1`) currently lacks the internal mechanisms to validate and retroactively enforce uniqueness constraints against existing graph edge data.

## Workaround / Mitigation
Currently, edge constraints must be defined prior to the initial schema `apply`. If they are missed, uniqueness must be handled entirely in the application layer, or the repository must be wiped and re-initialized from scratch.

---

# ISSUE REPORT: [OMNIGRAPH ENGINE] Edge Uniqueness Constraints Ignored on Insertion

## Status
**Open** | Priority: High | Type: Storage Engine / Core

## Description
Even when a `@unique(src, dst)` constraint is successfully applied to a graph schema at initialization, Omnigraph 0.4.1 does not actually enforce this constraint during query insertions. Duplicate edges can still be created between identical nodes.

### Symptoms
When executing `insert HAS_EVENT { from: $src, to: $dst }` multiple times with the exact same variables, the query succeeds each time without returning a conflict or constraint error, resulting in duplicate edges in the database.

### Root Cause Analysis (RCA)
Omnigraph v0.4.1 parses and stores the `@unique` constraint in the schema definition but lacks the runtime validation layer during edge insertion (`.txn` commit phase) to query existing edges and enforce uniqueness.

## Workaround / Mitigation
Edge uniqueness cannot be relied upon at the database level. Client applications must ensure idempotency (e.g., via persistent local caches) to prevent duplicate insertion queries from being sent to the server.
