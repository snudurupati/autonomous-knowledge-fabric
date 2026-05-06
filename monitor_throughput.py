# monitor_throughput.py
# Utility to monitor Knowledge Fabric ingestion rates in real-time.

import time
import sys
from pathlib import Path

# Add project root to sys.path
root_path = str(Path(__file__).resolve().parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from graph.omnigraph_client import OmnigraphClientWrapper

def calculate_throughput(duration_secs=60):
    """
    Samples Omnigraph platform stats over a duration to calculate 
    ingestion throughput (items per second).
    """
    client = OmnigraphClientWrapper()
    
    # Use branch head for monitoring to see absolute latest counts
    print(f"📊 Monitoring throughput for {duration_secs} seconds...")
    try:
        start_stats = client.get_platform_stats()
        start_time = time.time()
        
        if start_stats['events'] == 0 and start_stats['accounts'] == 0:
            print("⚠️ Warning: Initial counts are zero. Ensure the pipeline and Omnigraph server are running.")

        # Progress bar simulation
        for i in range(duration_secs):
            time.sleep(1)
            progress = (i + 1) / duration_secs
            bar = "█" * int(progress * 20) + "-" * (20 - int(progress * 20))
            sys.stdout.write(f"\r[{bar}] {int(progress * 100)}%")
            sys.stdout.flush()
        
        print("\n")
        end_stats = client.get_platform_stats()
        end_time = time.time()
        
        delta_t = end_time - start_time
        delta_acc = end_stats['accounts'] - start_stats['accounts']
        delta_evt = end_stats['events'] - start_stats['events']
        delta_rel = end_stats['relationships'] - start_stats['relationships']
        
        print("--- Ingestion Throughput Report ---")
        print(f"Window Duration: {delta_t:.1f}s")
        print(f"New Accounts:    {delta_acc} ({delta_acc/delta_t:.3f} acc/sec)")
        print(f"New Events:      {delta_evt} ({delta_evt/delta_t:.3f} evt/sec)")
        print(f"New Connections: {delta_rel} ({delta_rel/delta_t:.3f} rel/sec)")
        print("----------------------------------")
        print(f"Current Scale:   {end_stats['accounts']} accounts, {end_stats['events']} events")
        
        if delta_evt == 0:
            print("\n💡 Tip: If throughput is 0, the pipeline might be between SEC poll intervals (30s) or waiting to flush a batch (3s).")

    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")

if __name__ == "__main__":
    # Default to 60s monitor, or take arg
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    calculate_throughput(secs)
