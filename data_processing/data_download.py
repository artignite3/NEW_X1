"""
NEW_X1 — Data Download Pipeline
Downloads raw Cricsheet data and people registry.

Data Sources:
  - Cricsheet all matches zip / format-specific zips: https://cricsheet.org/downloads/
  - People register (unique IDs and player metadata): https://cricsheet.org/register/people.csv
"""

import io
import os
import zipfile
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
CRICKSHEET_DIR = RAW_DIR / "cricksheet_data"
ADDITIONAL_DIR = RAW_DIR / "additional_data"

CRICKSHEET_DIR.mkdir(parents=True, exist_ok=True)
ADDITIONAL_DIR.mkdir(parents=True, exist_ok=True)

PEOPLE_CSV_URL = "https://cricsheet.org/register/people.csv"
FORMAT_URLS = {
    "t20s": "https://cricsheet.org/downloads/t20s_json.zip",
    "odis": "https://cricsheet.org/downloads/odis_json.zip",
    "tests": "https://cricsheet.org/downloads/tests_json.zip",
}


def download_people_registry():
    """Downloads people.csv containing unique player IDs and metadata."""
    target_file = ADDITIONAL_DIR / "people.csv"
    if target_file.exists():
        print(f"✅ people.csv already exists at {target_file}")
        return

    print("📥 Downloading Cricsheet people registry (people.csv)...")
    try:
        r = requests.get(PEOPLE_CSV_URL, timeout=30)
        if r.status_code == 200:
            target_file.write_bytes(r.content)
            print(f"✅ Saved people.csv ({len(r.content):,} bytes)")
        else:
            print(f"⚠️ Failed to download people.csv, status: {r.status_code}")
    except Exception as e:
        print(f"❌ Error downloading people registry: {e}")


def download_format_zip(fmt: str, url: str):
    """Downloads and extracts format JSON zip into data/raw/cricksheet_data/{fmt}."""
    dest_dir = CRICKSHEET_DIR / fmt
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Check if files already extracted
    existing = list(dest_dir.glob("*.json"))
    if len(existing) > 50:
        print(f"✅ {fmt} JSON files already exist ({len(existing)} matches found in {dest_dir})")
        return

    print(f"📥 Downloading {fmt} matches from {url}...")
    try:
        r = requests.get(url, stream=True, timeout=120)
        if r.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            z.extractall(dest_dir)
            print(f"✅ Extracted {len(z.namelist()):,} match JSONs into {dest_dir}")
        else:
            print(f"⚠️ Failed to download {fmt}, status: {r.status_code}")
    except Exception as e:
        print(f"❌ Error downloading {fmt}: {e}")


def main():
    print("=" * 60)
    print("NEW_X1 — Cricsheet Raw Data Downloader")
    print("=" * 60)
    download_people_registry()
    for fmt, url in FORMAT_URLS.items():
        download_format_zip(fmt, url)
    print("\n✅ Data download step finished.")


if __name__ == "__main__":
    main()
