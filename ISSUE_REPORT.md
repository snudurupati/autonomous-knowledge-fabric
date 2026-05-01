# ISSUE REPORT: [BUG] 500 Internal Server Error on Branch Merge with Key Conflict

## Status
**Open** | Priority: Critical | Type: Backend / Reliability

## Description
The Omnigraph server returns a `500 Internal Server Error` when attempting to merge a side-branch into `main` using the `fast-forward` strategy if the branches have diverged in a way that creates a conflict on a `@key` property (e.g., `node_key` in the `Account` node). 

Instead of a graceful error (e.g., `409 Conflict`) or an automatic resolution (upsert/overwrite), the server's internal Lance-db state or merge coordinator fails, often leading to a crash or hanging state.

## Environment
- **OS**: Darwin (macOS)
- **Omnigraph Version**: 0.1.x (Local RustFS Bootstrap)
- **Storage**: RustFS (S3-native)

## Steps to Reproduce
1. Initialize a graph with a schema containing a `@key` constraint (e.g., `node_key: String @key`).
2. Create an entity in the `main` branch: `Account { name: "ITW", node_key: "itw_key" }`.
3. Create a side-branch `fragment-abc` from `main`.
4. In the side-branch, update or re-insert the same entity: `Account { name: "Illinois Tool Works", node_key: "itw_key" }`.
5. Attempt to merge the branch:
   ```bash
   curl -X POST http://127.0.0.1:8080/branches/merge \
     -H "Content-Type: application/json" \
     -d '{"source": "fragment-abc", "target": "main", "strategy": "fast-forward"}'
   ```

## Expected Behavior
The server should either:
1. Successfully merge the changes by treating the side-branch as an update to the `@key`.
2. Return a `400` or `409` error code with a message explaining the conflict.

## Actual Behavior
Server returns `500 Internal Server Error`. 
Logs show: `ERROR tower_http::trace::on_failure: response failed classification=Status code: 500 Internal Server Error`.
Internal logs indicate a failure in the `adopt_delta` or `adopt_full` phase of the Lance manifest update.

## Workaround
Implement a "Fast-Path" in the ingestion client that checks for high-confidence identifiers and performs a direct upsert to the `main` branch, bypassing the `branch` -> `merge` workflow for verified data.
