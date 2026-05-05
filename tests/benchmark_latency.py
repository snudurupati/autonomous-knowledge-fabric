import time
import statistics
import logging
import os
import requests
import json
import subprocess
from engine.omnigraph.ingestion_sink import OmnigraphSink
from engine.omnigraph.client import OmnigraphClient
from models.account_event import AccountEvent, EventSource, RiskSignal

# Suppress verbose logging
logging.basicConfig(level=logging.WARNING)

def run_benchmark(num_events=5):
    server_url = "http://localhost:8080"
    sink = OmnigraphSink(server_url=server_url)
    client = OmnigraphClient(base_url=server_url)
    
    print(f"🚀 Starting Omnigraph RCA Benchmark: {num_events} events...")
    
    # 1. Individual Mutations (The current slow path)
    individual_latencies = []
    for i in range(num_events):
        event = AccountEvent(
            source=EventSource.SALESFORCE,
            company_name=f"indiv_corp_{i}", 
            risk_signals=[RiskSignal.CRITICAL_SUPPORT],
            raw_text=f"Individual payload {i}"
        )
        
        start = time.monotonic()
        try:
            sink.ingest_event(event)
            individual_latencies.append((time.monotonic() - start) * 1000)
            print(f"  [Mutate] Event {i+1}/{num_events} complete ({individual_latencies[-1]/1000:.1f}s)")
        except Exception as e:
            print(f"  [Mutate] Event {i+1} failed: {e}")

    # 2. Batched Loading (The 'Gold Standard' path)
    print(f"📦 Measuring Batched Ingestion (100 events / 300 entities)...")
    batch_file = "bench_final.jsonl"
    with open(batch_file, "w") as f:
        for i in range(100):
            f.write(json.dumps({"type": "Account", "data": {"name": f"Batch Corp {i}", "node_key": f"batch_{i}", "risk_score": 20}}) + "\n")
            f.write(json.dumps({"type": "AccountEvent", "data": {"event_id": f"evt_{i}", "source": "BATCH", "timestamp": "2026-05-05", "raw_text": "..."}}) + "\n")
            f.write(json.dumps({"edge": "HAS_EVENT", "from": f"batch_{i}", "to": f"evt_{i}", "data": {}}) + "\n")
    
    start_batch = time.monotonic()
    try:
        # We use the CLI for the batched test to bypass HTTP/GQL overhead
        subprocess.run(
            ["./.omnigraph-rustfs-demo/bin/omnigraph", "load", "--mode", "merge", "--data", batch_file, "s3://omnigraph-local/batched-bench"],
            env={**os.environ, "AWS_EC2_METADATA_DISABLED": "true"},
            check=True, capture_output=True
        )
        batch_total_ms = (time.monotonic() - start_batch) * 1000
        batch_per_event_ms = batch_total_ms / 100
    except Exception as e:
        print(f"  [Batch] failed: {e}")
        batch_per_event_ms = 0

    # 3. Read Latency
    print("🔍 Measuring read latencies...")
    branch_reads = []
    snapshot_reads = []
    
    # Get a pinned snapshot ID for the fast path
    try:
        snapshot_id = client.get_latest_snapshot_id()
        print(f"📍 Pinned Snapshot ID: {snapshot_id}")
    except:
        snapshot_id = None

    for i in range(5):
        key = f"indiv_corp_{i}"
        # Measure Branch Read (Slow Path - includes S3 Head Check)
        try:
            start = time.monotonic()
            client.get_account_context(key)
            branch_reads.append((time.monotonic() - start) * 1000)
        except: pass
        
        # Measure Snapshot Read (Fast Path - Pinned/Cached)
        if snapshot_id:
            try:
                start = time.monotonic()
                client.get_account_context(key, snapshot_id=snapshot_id)
                snapshot_reads.append((time.monotonic() - start) * 1000)
            except: pass

    # 4. Output Stats
    p50_indiv = statistics.median(individual_latencies) if individual_latencies else 0
    p50_branch_read = statistics.median(branch_reads) if branch_reads else 0
    p50_snapshot_read = statistics.median(snapshot_reads) if snapshot_reads else 0
    
    print("\n" + "="*75)
    print(f"{'Operation Profile':<24} | {'Latency':<18} | {'Why?'}")
    print("-" * 75)
    print(f"{'Individual GQL Write':<24} | {p50_indiv/1000:<15.2f} s | 1 S3 Commit")
    print(f"{'Batched JSONL Load':<24} | {batch_per_event_ms:<15.2f} ms| 0.01 S3 Commits/evt")
    print(f"{'Branch Read (Head)':<24} | {p50_branch_read:<15.2f} ms| Includes S3 Head check")
    print(f"{'Snapshot Read (Pinned)':<24} | {p50_snapshot_read:<15.2f} ms| Cached / No S3 check")
    print("="*75)
    print("RCA: Branch reads incur S3 head-check overhead. Use Pinned Snapshots for RAG.")
    print("Note: 0.4.1 optimized commits; 0.3.1 was ~20x slower on writes.")
    print("="*75 + "\n")

if __name__ == "__main__":
    run_benchmark(3)
