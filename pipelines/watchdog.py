import os
import time
import signal
import subprocess

LOG_FILES = ["logs/scheduler.log"]
STATUS_FILE = "logs/WATCHDOG_STATUS.log"

def get_pids():
    pids = []
    # Processes to monitor
    commands = ["omnigraph-server", "sec_ingestion.py", "scheduler.py"]
    for cmd in commands:
        try:
            output = subprocess.check_output(['pgrep', '-f', cmd]).decode().strip()
            for pid_str in output.split('\n'):
                if pid_str:
                    pids.append(int(pid_str))
        except subprocess.CalledProcessError:
            pass # No process found
    return pids

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

def stop_all(pids):
    for pid in pids:
        if is_running(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

def main():
    # Allow time for all background processes to start before capturing PIDs
    time.sleep(15)
    initial_pids = get_pids()
    
    with open(STATUS_FILE, "w") as f:
        f.write(f"Watchdog started at {time.ctime()} monitoring PIDs {initial_pids}\n")

    while True:
        current_pids = [pid for pid in initial_pids if is_running(pid)]
        
        # If any of the initially tracked processes died
        if len(current_pids) < len(initial_pids):
            with open(STATUS_FILE, "a") as f:
                f.write(f"[{time.ctime()}] STOPPING: One or more processes died. Expected {len(initial_pids)} but found {len(current_pids)} running.\n")
            stop_all(current_pids)
            break
            
        # Check for errors in logs
        error_found, reason = check_errors()
        if error_found:
            with open(STATUS_FILE, "a") as f:
                f.write(f"[{time.ctime()}] STOPPING: {reason}\n")
            stop_all(current_pids)
            break
            
        time.sleep(60)

if __name__ == "__main__":
    main()
