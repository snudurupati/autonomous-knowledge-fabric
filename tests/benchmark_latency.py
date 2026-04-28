import time
import numpy as np
from typing import List
from engine.omnigraph.ingestion_sink import OmnigraphSink
from engine.omnigraph.client import OmnigraphClient
from pipelines.synthetic_crm import SalesforceEventGenerator, ZendeskEventGenerator
from models.account_event import AccountEvent

def benchmark_omnigraph():
    sink = OmnigraphSink()
    client = OmnigraphClient()
    sf_gen = SalesforceEventGenerator()
    zd_gen = ZendeskEventGenerator()
    
    num_events = 100
    events: List[AccountEvent] = []
    
    # Generate 100 synthetic events
    for i in range(num_events):
        if i % 2 == 0:
            events.append(sf_gen.generate())
        else:
            events.append(zd_gen.generate())
            
    print(f"Starting Omnigraph Benchmark with {num_events} events...")
    
    branch_creation_latencies = []
    merge_latencies = []
    read_latencies = []
    
    # 1. Ingest (Branch Creation)
    branches = []
    for event in events:
        t0 = time.perf_counter()
        branch_id = sink.ingest_unverified_entity(event)
        t1 = time.perf_counter()
        if branch_id:
            branches.append((branch_id, event.company_name))
            branch_creation_latencies.append((t1 - t0) * 1000)
            
    # 2. Evaluate and Merge (S3 Commit)
    for branch_id, _ in branches:
        # Simulate high evidence score to force a merge
        t0 = time.perf_counter()
        sink.evaluate_and_merge(branch_id, evidence_score=95)
        t1 = time.perf_counter()
        merge_latencies.append((t1 - t0) * 1000)
        
    # 3. Read (Snapshot-Pinned)
    latest_snapshot = client.get_latest_snapshot()
    for _, company_name in branches:
        t0 = time.perf_counter()
        client.get_account_context(company_name, snapshot_id=latest_snapshot)
        t1 = time.perf_counter()
        read_latencies.append((t1 - t0) * 1000)
        
    def get_stats(data):
        if not data: return 0, 0
        return np.percentile(data, 50), np.percentile(data, 99)

    p50_create, p99_create = get_stats(branch_creation_latencies)
    p50_merge, p99_merge = get_stats(merge_latencies)
    p50_read, p99_read = get_stats(read_latencies)
    
    print("\n" + "="*60)
    print(f"{'Metric':<30} | {'P50 (ms)':<10} | {'P99 (ms)':<10}")
    print("-" * 60)
    print(f"{'Omnigraph Branch Create':<30} | {p50_create:<10.2f} | {p99_create:<10.2f}")
    print(f"{'Omnigraph Merge (S3 Commit)':<30} | {p50_merge:<10.2f} | {p99_merge:<10.2f}")
    print(f"{'Omnigraph Pinned Read':<30} | {p50_read:<10.2f} | {p99_read:<10.2f}")
    print("-" * 60)
    print(f"{'Legacy Memgraph Write (P50)':<30} | {'1.50':<10} | {'N/A':<10}")
    print("="*60)
    
    print("\nAnalysis:")
    if p50_merge > 5:
        print(f"[-] Omnigraph S3 Commit ({p50_merge:.2f}ms) is slower than Memgraph Bolt (~1.5ms).")
        print("    This is expected due to S3 consistency/IO overhead vs in-memory Bolt.")
    else:
        print(f"[+] Omnigraph S3 Commit ({p50_merge:.2f}ms) is surprisingly competitive with Memgraph!")

if __name__ == "__main__":
    benchmark_omnigraph()
