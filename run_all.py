"""
NEW_X1 — Universal Service Launcher
Runs all 3 platform services together in a single terminal process:
  1. FastAPI Backend        -> http://localhost:8000  (Docs: /docs)
  2. Next.js Product UI     -> http://localhost:3000
  3. Streamlit Model UI     -> http://localhost:8502

Press Ctrl + C in this terminal to stop all services simultaneously.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

# Project root directory
BASE_DIR = Path(__file__).resolve().parent

# Auto-detect virtual environment python
VENV_PYTHON = BASE_DIR / "env" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    # Fallback to current python interpreter
    VENV_PYTHON = Path(sys.executable)

SERVICES = [
    {
        "name": "FastAPI Backend",
        "cmd": [
            str(VENV_PYTHON), "-m", "uvicorn",
            "model.model_fastapi:app",
            "--host", "0.0.0.0",
            "--port", "8000"
        ],
        "url": "http://localhost:8000",
        "docs": "http://localhost:8000/docs",
        "port": 8000
    },
    {
        "name": "Product UI (Next.js)",
        "cmd": [
            "npm.cmd", "run", "dev"
        ],
        "cwd": str(BASE_DIR / "frontend"),
        "url": "http://localhost:3000",
        "port": 3000
    },
    {
        "name": "Model Evaluation UI (Streamlit)",
        "cmd": [
            str(VENV_PYTHON), "-m", "streamlit", "run",
            "UI/model_ui.py",
            "--server.port", "8502",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        ],
        "url": "http://localhost:8502",
        "port": 8502
    }
]


def print_banner():
    banner = """
======================================================================
           NEW_X1 - CRICKET PERFORMANCE INTELLIGENCE PLATFORM
                       ALL SERVICES LAUNCHER
======================================================================
  [1] FastAPI Backend        : http://localhost:8000
      Interactive API Docs   : http://localhost:8000/docs
  [2] Product UI (Next.js)   : http://localhost:3000
  [3] Model UI (Streamlit)   : http://localhost:8502
======================================================================
  Logs will stream below. Press Ctrl + C to stop all services.
======================================================================
"""
    print(banner, flush=True)


def main():
    print_banner()

    processes = []

    def shutdown(sig=None, frame=None):
        print("\n\n[INFO] Shutting down all services...", flush=True)
        for p, s in processes:
            print(f"  Stopping {s['name']} (PID {p.pid})...", flush=True)
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print("[OK] All services stopped cleanly. Goodbye!\n", flush=True)
        sys.exit(0)

    # Register graceful termination handlers
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Launch each service
    for s in SERVICES:
        print(f"[STARTING] {s['name']} on port {s['port']}...", flush=True)
        try:
            proc = subprocess.Popen(
                s["cmd"],
                cwd=s.get("cwd", str(BASE_DIR)),
                shell=False
            )
            processes.append((proc, s))
            time.sleep(1.2)  # Short delay to stagger port bindings
        except Exception as e:
            print(f"[ERROR] Failed to start {s['name']}: {e}", flush=True)

    print("\n[READY] All 3 services are active and running!\n", flush=True)

    # Monitor processes
    try:
        while True:
            for p, s in processes:
                ret = p.poll()
                if ret is not None:
                    print(f"[WARNING] {s['name']} exited unexpectedly with code {ret}")
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
