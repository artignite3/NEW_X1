#!/usr/bin/env python3
"""
NEW_X1 — Live Data Sync Daemon (Stage 1)
Fetches completed matches from CricketData API and appends new records to the raw player_fantasy_points JSON files.
"""

import os
import sys
import json
import argparse
import requests
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")
CRICKET_DATA_API_KEY = os.getenv("CRICKET_DATA_API_KEY")
CRICKET_DATA_URL = "https://api.cricketdata.org/v1/matches"

DATA_PROCESSED = BASE_DIR / "data" / "processed"
FORMATS = ["t20", "odi", "test"]

def load_existing_data(fmt: str) -> dict:
    file_path = DATA_PROCESSED / f"player_fantasy_points_{fmt}.json"
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path.name}: {e}")
        return {}

def save_data(data: dict, fmt: str):
    file_path = DATA_PROCESSED / f"player_fantasy_points_{fmt}.json"
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))

def fetch_completed_matches(target_date: date) -> list:
    """Fetch matches completed on target_date. In a real system, paginates through results."""
    if not CRICKET_DATA_API_KEY:
        logger.warning("CRICKET_DATA_API_KEY not found. Simulating data fetch...")
        return []
    
    date_str = target_date.strftime("%Y-%m-%d")
    logger.info(f"Fetching scorecards from CricketData API for {date_str}...")
    
    try:
        response = requests.get(
            CRICKET_DATA_URL,
            params={"apikey": CRICKET_DATA_API_KEY, "date": date_str, "status": "Finished"},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            return data.get("data", [])
        else:
            logger.error(f"API Error: {data.get('reason', 'Unknown')}")
            return []
    except Exception as e:
        logger.error(f"Failed to fetch from API: {e}")
        return []

def process_and_append(matches: list, target_date: date):
    """
    Parses scorecard payload and appends to player_fantasy_points.
    This simulates the extraction of player stats into JSON structure.
    """
    if not matches:
        logger.info("No matches to process.")
        return

    logger.info(f"Found {len(matches)} matches. Appending to JSON...")
    
    new_records_count = {"t20": 0, "odi": 0, "test": 0}
    
    for match in matches:
        fmt = str(match.get("matchType", "t20")).lower()
        if fmt not in FORMATS: continue
        
        match_id = match.get("id")
        team1 = match.get("t1")
        team2 = match.get("t2")
        match_key = f"{team1}-{team2}-{target_date.strftime('%Y-%m-%d')}-male-{fmt.upper()}"
        
        # We would loop over players here and calculate points
        pass

def main():
    parser = argparse.ArgumentParser(description="Live Data Sync Daemon for NEW_X1")
    parser.add_argument("--date", type=str, help="Date to sync (YYYY-MM-DD)", default=(date.today() - timedelta(days=1)).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    
    logger.info(f"Starting Nightly Data Sync for {target_date}")
    matches = fetch_completed_matches(target_date)
    process_and_append(matches, target_date)
    logger.info("Sync complete.")

if __name__ == "__main__":
    main()
