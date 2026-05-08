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
