#!/usr/bin/env python3

import os
import json
import logging
from plotly import data
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import Counter
from soupsieve import match

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


RAPID_API_KEY = os.getenv("RAPID_API_KEY")

RAPID_API_HOST = "cricbuzz-cricket.p.rapidapi.com"

RAPID_API_URL = (
    "https://cricbuzz-cricket.p.rapidapi.com/"
    "schedules/v1/list"
)
EXCLUDED_SERIES = [
    "Madhya Pradesh Premier League",
    "Andhra Premier League",
    "Maharaja Trophy",
    "Continental Cup",
    "Americas Sub Regional Qualifier",
    "Kwibuka",
    "Central Europe Cup",
    "Namibia T20I Tri-Series",
    "Karnataka Premier League",
    "Bihar Cricket League",
    "Duleep Trophy",
    "Deodhar Trophy",
    "Irani Cup",
    "County Championship",
    "T20 Blast",
    "Royal London One-Day Cup",
    "Sheffield Shield",
    "European Cricket League",
    "Global T20 Canada",
    "Minor League Cricket",
    "European T20 Premier League",
    "Lanka Premier League",
    "Bangladesh Premier League",
    "Bengal Premier League",
    "Afghanistan Premier League",
    "Zambia T20 League",
    "Zimbabwe Domestic Twenty20 Competition",
    "Zimbabwe Domestic One-Day Competition",
    "Zimbabwe Domestic First-Class Competition",
    "Kashmir Premier League",
    "T10 League",
    
]
PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

OUTPUT_DIR = os.path.join(
    PROJECT_ROOT,
    "data",
    "future_matches"
)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "upcoming_matches.json"
)

RAW_RESPONSE_FILE = os.path.join(
    OUTPUT_DIR,
    "raw_api_response.json"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_matches():

    if not RAPID_API_KEY:
        raise ValueError("RAPID_API_KEY not found")

    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "cricbuzz-cricket.p.rapidapi.com"
    }

    endpoints = [
        "https://cricbuzz-cricket.p.rapidapi.com/schedule/v1/international",
        "https://cricbuzz-cricket.p.rapidapi.com/schedule/v1/league",
        "https://cricbuzz-cricket.p.rapidapi.com/schedule/v1/women"
    ]

    all_matches = []
    seen_ids = set()

    BLOCKED_SERIES = [
        "Madhya Pradesh Premier League",
        "Andhra Premier League",
        "Maharaja Trophy",
        "Continental Cup",
        "Sub Regional Qualifier",
        "European Cricket",
        "ECS",
        "ECL",
        "National T20 Cup"
    ]

    for endpoint in endpoints:

        logger.info(f"Fetching: {endpoint}")

        try:

            response = requests.get(
                endpoint,
                headers=headers,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            logger.info(
                f"Days found: "
                f"{len(data.get('matchScheduleMap', []))}"
            )

            for day in data.get(
                "matchScheduleMap",
                []
            ):

                wrapper = day.get(
                    "scheduleAdWrapper",
                    {}
                )

                for series in wrapper.get(
                    "matchScheduleList",
                    []
                ):

                    series_name = series.get(
                        "seriesName",
                        ""
                    )

                    # Skip unwanted leagues
                    if (
                        any(
                            blocked.lower()
                            in series_name.lower()
                            for blocked in BLOCKED_SERIES
                        )
                        and
                        "T20 Mumbai" not in series_name
                    ):
                        continue

                    for match in series.get("matchInfo", []):
                    
                        match["seriesName"] = series_name
                    
                        match_id = match.get("matchId")
                    
                        if (
                            not match_id
                            or match_id in seen_ids
                        ):
                            continue
                        
                        seen_ids.add(match_id)
                    
                        all_matches.append(match)
    
        except Exception as e:

            logger.error(
                f"Failed endpoint "
                f"{endpoint}: {e}"
            )

    logger.info(
        f"TOTAL MATCHES FETCHED: "
        f"{len(all_matches)}"
    )

    return all_matches

def map_matches(matches_data):

    mapped_matches = []

    for match in matches_data:

        try:

            start_dt = datetime.utcfromtimestamp(
                int(
                    match.get(
                        "startDate",
                        0
                    )
                ) / 1000
            )

            mapped_matches.append({

                "match_id":
                    match.get(
                        "matchId"
                    ),

                "series_id":
                    match.get(
                        "seriesId"
                    ),

                "series":
                    match.get(
                        "seriesName",
                        ""
                    ),

                "team1":
                    match.get(
                        "team1",
                        {}
                    ).get(
                        "teamName",
                        ""
                    ),

                "team2":
                    match.get(
                        "team2",
                        {}
                    ).get(
                        "teamName",
                        ""
                    ),

                "match_type":
                    str(
                        match.get(
                            "matchFormat",
                            ""
                        )
                    ).upper(),

                "venue":
                    (
                        f"{match.get('venueInfo', {}).get('ground', '')}, "
                        f"{match.get('venueInfo', {}).get('city', '')}"
                    ),

                "date":
                    start_dt.strftime(
                        "%Y-%m-%d"
                    ),

                "datetime_gmt":
                    start_dt.isoformat(),

                "status":
                    match.get(
                        "stateTitle",
                        "Upcoming"
                    ),

                "fantasy_enabled":
                    True,

                # True squad availability is determined later by squad_fetcher;
                # the backend re-derives this from upcoming_squads.json.
                "has_squad":
                    False,

                "match_started":
                    False,

                "match_ended":
                    False
            })

        except Exception as e:

            logger.error(
                f"Mapping error: {e}"
            )

    logger.info(
        f"MAPPED MATCHES: "
        f"{len(mapped_matches)}"
    )

    return mapped_matches

def filter_future_matches(matches):

    today = datetime.utcnow().date()
    end_date = today + timedelta(days=7)

    future_matches = []

    seen_ids = set()

    for match in matches:

        try:

            match_date = datetime.strptime(
                match["date"],
                "%Y-%m-%d"
            ).date()

            if not (today <= match_date <= end_date):
                continue

            if (
                match["team1"].upper() == "TBC"
                or
                match["team2"].upper() == "TBC"
            ):
                continue

            if match["match_type"] not in [
                "T20",
                "ODI",
                "TEST"
            ]:
                continue

            if match["match_id"] in seen_ids:
                continue

            seen_ids.add(match["match_id"])

            future_matches.append(match)

        except Exception:
            pass

    return future_matches

def save_matches(matches):

    output = {

        "fetched_at":
            datetime.now().isoformat(),

        "source":
            "cricapi",

        "match_count":
            len(matches),

        "matches":
            matches
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False
        )

    logger.info(
        f"Saved {len(matches)} matches to {OUTPUT_FILE}"
    )

def main():

    logger.info(
        "Starting schedule fetcher..."
    )

    matches_data = fetch_matches()
    print(f"RAW MATCHES FROM API: {len(matches_data)}")
    mapped_matches = map_matches(
        matches_data
    )
    print(f"MAPPED MATCHES: {len(mapped_matches)}")
    future_matches = (
        filter_future_matches(
            mapped_matches
        )
    )

    save_matches(
        future_matches
    )
    format_counts = Counter(
        m.get("match_type", "UNKNOWN")
        for m in future_matches
    )
    print("\n========== SUMMARY ==========")
    print(f"Total Matches : {len(future_matches)}")
    print(f"T20 Matches   : {format_counts.get('T20', 0)}")
    print(f"ODI Matches   : {format_counts.get('ODI', 0)}")
    print(f"TEST Matches  : {format_counts.get('TEST', 0)}")
    print("=============================")    

if __name__ == "__main__":
    main()