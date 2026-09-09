import os
import psutil
import requests
import time
import subprocess
import sys

def get_process_memory(pid):
    try:
        process = psutil.Process(pid)
        return process.memory_info().rss / (1024 * 1024)
    except psutil.NoSuchProcess:
        return 0

def wait_for_server():
    for _ in range(30):
        try:
            r = requests.get("http://127.0.0.1:8000/health")
            if r.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def main():
    print("Starting uvicorn server...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "sanket.api:app", "--host", "127.0.0.1", "--port", "8000"], env=env)
    
    if not wait_for_server():
        print("Server failed to start")
        proc.terminate()
        return

    print(f"Startup RSS: {get_process_memory(proc.pid):.2f} MB")

    endpoints = [
        "/api/dashboard/summary",
        "/api/projects?limit=10",
        "/api/projects/PRJ-12345",
        "/api/projects/PRJ-12345/replay"
    ]
    
    for ep in endpoints:
        print(f"Hitting {ep}...")
        requests.get(f"http://127.0.0.1:8000{ep}")
        print(f"RSS after {ep}: {get_process_memory(proc.pid):.2f} MB")

    print(f"Peak RSS during run: {get_process_memory(proc.pid):.2f} MB")
    proc.terminate()

if __name__ == "__main__":
    main()
