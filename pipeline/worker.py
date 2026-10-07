"""Scheduled refresh uses private scratch space; failures never change serving files."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from dotenv import load_dotenv
from pipeline.object_store import configured_store, json_bytes
from pipeline.releases import restore_release, publish_release
from run_daily_sync import run_sync


def run_worker(store=None, *, skip_download=False, historical_only=False):
    store = store or configured_store()
    report = {"status": "failed", "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        with tempfile.TemporaryDirectory(prefix="new-x1-sync-") as folder:
            old, manifest, recovery = restore_release(store, Path(folder) / "cache")
            stage = Path(folder) / "stage"
            shutil.copytree(old, stage)
            environment = dict(os.environ, NEW_X1_DATA_ROOT=str(stage / "data"),
                NEW_X1_MODEL_ROOT=str(stage / "model_artifacts"), PIPELINE_STAGING="true")
            report = run_sync(skip_download, historical_only, environment)
            report["previous_release"] = manifest["release_id"]
            if report["status"] == "failed": return report
            selected_pointer = {"current": recovery["selected"]}
            published = publish_release(stage, store, pointer=selected_pointer, etag=recovery["etag"], status=report["status"])
            report["release_id"] = published["release_id"]
            return report
    except Exception as error:
        # Logs contain error classes, never credentials, signed URLs or request headers.
        report.update(status="failed", error=type(error).__name__)
        return report
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        try:
            store.write("latest_run.json", json_bytes(report))
        except Exception as error:
            report.update(status="failed", report_error=type(error).__name__)


def main():
    import argparse
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--historical-only", action="store_true")
    args = parser.parse_args()
    report = run_worker(skip_download=args.skip_download, historical_only=args.historical_only)
    print(json.dumps({key: value for key, value in report.items() if key != "stages"}))
    # Degraded runs preserve data but must still trigger the scheduler's failure notification.
    raise SystemExit(0 if report["status"] == "ok" else 1)


if __name__ == "__main__": main()
