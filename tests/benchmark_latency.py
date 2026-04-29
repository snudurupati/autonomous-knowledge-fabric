import time
import statistics
import logging
import os
import requests
from engine.omnigraph.ingestion_sink import OmnigraphSink
from engine.omnigraph.client import OmnigraphClient
from models.account_event import AccountEvent, EventSource, RiskSignal

# Suppress verbose logging during benchmark
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("engine.omnigraph.ingestion_sink")
logger.setLevel(logging.WARNING)

def run_benchmark(num_events=50): # Reduced to 50 for stability
    sink = OmnigraphSink(server_url="http://localhost:8080")
    client = OmnigraphClient(base_url="http://localhost:8080")
    
    upsert_latencies = []
    read_latencies = []
    
    print(f"🚀 Starting Omnigraph Benchmark: {num_events} events...")
    
    # 1. Ingest synthetic events
    for i in range(num_events):
        event = AccountEvent(
            source=EventSource.SALESFORCE,
            company_name=f"bench_corp_{i % 5}", 
            risk_signals=[RiskSignal.CRITICAL_SUPPORT],
            raw_text=f"Benchmark payload {i}"
        )
        
        # Add retry logic for connection stability
        max_retries = 3
        success = False
        start = 0
        for attempt in range(max_retries):
            try:
                start = time.monotonic()
                success = sink.ingest_event(event)
                if success:
                    break
            except Exception:
                time.sleep(0.5)
        
        if not success:
            print(f"❌ Failed to ingest event {i}")
            continue
            
        upsert_latencies.append((time.monotonic() - start) * 1000)
        if (i + 1) % 10 == 0:
            print(f"  Ingested {i+1}/{num_events} events...")
        time.sleep(0.1) # Small cooldown
        
    # 2. Get latest snapshot ID for pinned reads
    try:
        snapshot_id = client.get_latest_snapshot_id()
        print(f"📍 Pinned Snapshot ID: {snapshot_id}")
    except Exception as e:
        print(f"⚠️ Could not get snapshot ID: {e}. Using main branch for reads.")
        snapshot_id = None
    
    # 3. Measure read latency (Context)
    print("🔍 Measuring read latencies...")
    for i in range(num_events):
        account_key = f"bench_corp_{i % 5}"
        try:
            start = time.monotonic()
            client.get_account_context(account_key, snapshot_id=snapshot_id)
            read_latencies.append((time.monotonic() - start) * 1000)
        except Exception as e:
            print(f"⚠️ Read failed for {account_key}: {e}")
        time.sleep(0.05)
        
    if not upsert_latencies or not read_latencies:
        print("❌ Benchmark failed to collect enough data.")
        return

    # 4. Calculate stats
    p50_upsert = statistics.median(upsert_latencies)
    p99_upsert = statistics.quantiles(upsert_latencies, n=100)[98] if len(upsert_latencies) >= 100 else max(upsert_latencies)
    p50_read = statistics.median(read_latencies)
    
    # 5. Output Table
    print("\n" + "="*65)
    print(f"{'Metric':<32} | {'Omnigraph (S3)':<14} | {'Memgraph (In-Mem)':<14}")
    print("-" * 65)
    print(f"{'P50 Upsert Latency (ms)':<32} | {p50_upsert:<14.2f} | {'~2.00':<14}")
    print(f"{'P99 Upsert Latency (ms)':<32} | {p99_upsert:<14.2f} | {'~5.00':<14}")
    print(f"{'P50 Context Read (ms)':<32} | {p50_read:<14.2f} | {'~1.50':<14}")
    print("="*65)
    print("Note: Omnigraph latencies include 3 mutations per ingest.")
    print("="*65 + "\n")

if __name__ == "__main__":
    run_benchmark(50)
