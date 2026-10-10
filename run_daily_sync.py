"""Bounded, observable sync: historical data, features, fixtures and squads."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
from dotenv import load_dotenv
from project_paths import data_root
from pipeline.runtime import atomic_json, exclusive_lock, redact

ROOT = Path(__file__).resolve().parent


def run_stage(module, arguments=(), *, timeout=1800, attempts=1, required=True, environment=None):
    environment = dict(environment or os.environ)
    start = time.monotonic()
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run([sys.executable, "-m", module, *arguments], cwd=ROOT,
                env=environment, timeout=timeout, capture_output=True, text=True, encoding="utf-8", errors="replace")
            last = redact((result.stdout + result.stderr)[-4000:], environment)
            if result.returncode == 0:
                return {"name": module, "status": "ok", "attempts": attempt,
                        "seconds": round(time.monotonic() - start, 2), "output": last}
        except subprocess.TimeoutExpired:
            last = "Stage exceeded its configured timeout"
        except OSError:
            last = "Stage process could not start"
    return {"name": module, "status": "failed" if required else "degraded", "attempts": attempts,
            "seconds": round(time.monotonic() - start, 2), "output": last}


def run_sync(skip_download=False, historical_only=False, environment=None):
    environment = dict(environment or os.environ)
    if environment.get("APP_ENV", "production") in {"staging", "production"} and environment.get("PIPELINE_STAGING") != "true":
        raise ValueError("Deployed sync must run through the isolated release worker")
    root = Path(environment.get("NEW_X1_DATA_ROOT", str(data_root())))
    root.mkdir(parents=True, exist_ok=True)
    report = {"run_id": uuid4().hex, "status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "stages": []}
    with exclusive_lock(root / "pipeline.lock"):
        status_file = root / "pipeline_status.json"
        atomic_json(status_file, report)
        stages = []
        if not skip_download:
            stages.append(("data_processing.data_download", (), 1800, 2, True))
        stages.extend([("data_processing.cricsheet_ingestor", (), 1800, 1, True),
                       ("intelligence.build_venue_history", (), 300, 1, False),
                       ("data_processing.incremental_feature_append", (), 1800, 1, True)])
        if not historical_only:
            stages.extend([("data.future_matches.schedule_fetcher", (), 180, 1, False),
                ("data.future_matches.cricapi_sync", ("--days", "2"), 120, 1, False),
                ("data.future_matches.squad_fetcher", ("--max-requests", environment.get("SQUAD_REQUEST_BUDGET", "3")), 300, 1, False)])
        for module, arguments, timeout, attempts, required in stages:
            outcome = run_stage(module, arguments, timeout=timeout, attempts=attempts, required=required, environment=environment)
            report["stages"].append(outcome)
            atomic_json(status_file, report)
            print(f"{module}: {outcome['status']} ({outcome['seconds']}s)", flush=True)
            if outcome["status"] == "failed":
                report["status"] = "failed"
                break
        else:
            report["status"] = "degraded" if any(s["status"] == "degraded" for s in report["stages"]) else "ok"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(status_file, report)
    return report


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true", help="Use existing raw archives for offline verification")
    parser.add_argument("--historical-only", action="store_true", help="Skip live providers during offline verification")
    args = parser.parse_args()
    try:
        report = run_sync(args.skip_download, args.historical_only)
        raise SystemExit(1 if report["status"] == "failed" else 0)
    except (OSError, ValueError) as error:
        print(f"Pipeline unavailable: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__": main()
