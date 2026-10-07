#!/usr/bin/env python3
"""
NEW_X1 — Nightly Cron Sync
Executes the live data sync daemon and the incremental feature update
to continuously roll the test dataset forward.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable

def run_script(script_path: Path):
    logger.info(f"Executing: {script_path.name}")
    try:
        result = subprocess.run([PYTHON_EXE, str(script_path)], check=True, capture_output=True, text=True, encoding="utf-8")
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to execute {script_path.name}\n{e.stderr}")
        sys.exit(1)

def main():
    logger.info("=" * 60)
    logger.info(f"NEW_X1 Nightly Pipeline Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    download_script = BASE_DIR / "data_processing" / "data_download.py"
    ingestor_script = BASE_DIR / "data_processing" / "cricsheet_ingestor.py"
    append_script = BASE_DIR / "data_processing" / "incremental_feature_append.py"

    run_script(download_script)
    run_script(ingestor_script)
    run_script(append_script)

    # Fixture feed refresh (non-fatal — analysis works on the last known feed)
    fixture_sync = BASE_DIR / "data" / "future_matches" / "cricapi_sync.py"
    if fixture_sync.exists():
        logger.info("Refreshing imminent fixtures (cricketdata.org fallback)...")
        try:
            result = subprocess.run(
                [PYTHON_EXE, str(fixture_sync), "--days", "2"],
                check=False, capture_output=True, text=True, encoding="utf-8", timeout=120,
            )
            logger.info(result.stdout or "  (no output)")
            if result.returncode != 0:
                logger.warning(f"Fixture sync finished with code {result.returncode} — continuing")
        except Exception as e:
            logger.warning(f"Fixture sync skipped: {e}")

    # Full-window fixture/squad refresh requires RAPID_API_KEY (Cricbuzz):
    #   python data/future_matches/schedule_fetcher.py && python data/future_matches/squad_fetcher.py

    
    logger.info("=" * 60)
    logger.info(f"NEW_X1 Nightly Pipeline Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
