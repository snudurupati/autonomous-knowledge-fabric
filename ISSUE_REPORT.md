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
