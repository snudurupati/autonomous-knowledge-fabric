# Migrating Omnigraph from RustFS to MinIO

This document details the process for migrating a local Omnigraph repository from a RustFS-backed S3 simulator to a standalone MinIO server.

## Rationale: Why Migrate?

While RustFS is excellent for zero-config local development, the AKF project hit several technical bottlenecks as the graph grew in complexity:

1.  **Metadata Concurrency Issues:** RustFS struggles with high-volume concurrent metadata requests. During parallel ingestion or rapid branching, this led to "False 404" (NoSuchKey) and "NoSuchBucket" anomalies even when the data existed.
2.  **S3 Consistency Lag:** AKF requires strict consistency for manifest updates. MinIO provides a more robust implementation of S3 consistency models, reducing the frequency of `409 Conflict` errors during branch merges.
3.  **Stability:** The append-only Lance backend used by Omnigraph is sensitive to mid-commit crashes. MinIO's production-grade storage engine provides better protection against the "Dangling Manifest" corruption observed in heavy RustFS stress tests.

## Overview

The migration uses an S3-to-S3 "side-car" approach. Because RustFS stores objects as directories on the local filesystem (with `xl.meta` files), a simple `cp` or `aws s3 sync` of the local folder to MinIO will result in a corrupted repository structure. Instead, we serve the old data through a temporary RustFS instance and sync via the S3 API.

## Prerequisites

- **Docker** installed and running.
- **AWS CLI** installed.
- **MinIO** server running (default port `9000`).

## Step 1: Start Temporary RustFS Source

Map the existing local data to a temporary port (e.g., `9010`) so it doesn't collide with your MinIO instance.

```bash
# Define your local storage path
LOCAL_DATA="/Users/snudurupati/Projects/autonomous-knowledge-fabric/.omnigraph-rustfs-demo/rustfs-data"

docker run -d \
  --name rustfs-migration-source \
  -p 9010:9000 \
  -v $LOCAL_DATA:/data \
  rustfs/rustfs:latest /entrypoint.sh /data
```

## Step 2: Configure Environment

Ensure your credentials for both the source (RustFS) and destination (MinIO) are ready.

**Destination (.env.omni):**
```bash
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_ENDPOINT_URL=http://127.0.0.1:9000
```

**Source (RustFS default):**
- Access Key: `rustfsadmin`
- Secret Key: `rustfsadmin`

## Step 3: Perform S3-to-S3 Sync

We first download the data to a flattened local directory, then upload it to MinIO. This ensures the S3 API handles the conversion from the RustFS "backend" format to standard objects.

```bash
mkdir migration_temp

# 1. Download from RustFS (Source)
export AWS_ACCESS_KEY_ID=rustfsadmin
export AWS_SECRET_ACCESS_KEY=rustfsadmin
aws s3 sync s3://omnigraph-local ./migration_temp --endpoint-url http://127.0.0.1:9010

# 2. Upload to MinIO (Destination)
source .env.omni
aws s3 mb s3://omnigraph-local --endpoint-url $AWS_ENDPOINT_URL
aws s3 sync ./migration_temp s3://omnigraph-local --endpoint-url $AWS_ENDPOINT_URL --delete
```

## Step 4: Update Configuration

Update your `omnigraph.yaml` to point to the new repository URI.

```yaml
graphs:
  local_s3:
    uri: s3://omnigraph-local/crm-repo
```

## Step 5: Verify and Cleanup

Run an Omnigraph command to verify connectivity and data integrity.

```bash
./.omnigraph-rustfs-demo/bin/omnigraph commit list --target local_s3
```

Once verified, remove the temporary container and migration files:

```bash
docker rm -f rustfs-migration-source
rm -rf migration_temp
```
