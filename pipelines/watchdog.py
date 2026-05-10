import os
import time
import signal
import subprocess

# Update with new PIDs
# Server: 45337, Scheduler: 45351, Ingestion: 45352
PIDS = [45337, 45351, 45352]
LOG_FILES = ["logs/scheduler.log"]
STATUS_FILE = "logs/WATCHDOG_STATUS.log"

def is_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def check_errors():
    for log in LOG_FILES:
        if os.path.exists(log):
            try:
                # Use subprocess to tail and check for errors
                output = subprocess.check_output(['tail', '-n', '20', log]).decode().lower()
                if "error" in output or "conflict" in output:
                    return True, f"Found error in {log}"
            except Exception:
                pass
    return False, ""

def stop_all():
    for pid in PIDS:
        if is_running(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

with open(STATUS_FILE, "w") as f:
    f.write(f"Watchdog started at {time.ctime()} monitoring PIDs {PIDS}\n")

while True:
    running_pids = [pid for pid in PIDS if is_running(pid)]
    
    # If server or ingestion died
    if len(running_pids) < len(PIDS):
        with open(STATUS_FILE, "a") as f:
            f.write(f"[{time.ctime()}] STOPPING: One or more processes died. Running: {running_pids}\n")
        stop_all()
        break
        
    # Check for errors
    error_found, reason = check_errors()
    if error_found:
        with open(STATUS_FILE, "a") as f:
            f.write(f"[{time.ctime()}] STOPPING: {reason}\n")
        stop_all()
        break
        
    time.sleep(60)
