"""
NEW_X1 — Fixture Sync (cricketdata.org free-tier fallback)

The primary feed (Cricbuzz via RapidAPI, see schedule_fetcher.py) requires
RAPID_API_KEY. This module provides what the configured CRICKET_DATA_API_KEY
free tier genuinely supports:

  - GET /v1/currentMatches (1 hit): matches that are live or starting within
    the next ~24h. International T20/ODI/Test fixtures not yet started are
    synced into upcoming_matches.json.

  - GET /v1/matchSquad: plan-locked on the free tier ("Invalid API requested")
    — attempted once per run and disabled for the rest of the run if the plan
    rejects it. Squads therefore come from the RapidAPI fetcher, or remain
    pending (the platform degrades gracefully to prior-based analysis).

Usage:
  python data/future_matches/cricapi_sync.py [--days 2]
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CRICKET_DATA_API_KEY")
BASE = "https://api.cricapi.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
MATCHES_FILE = os.path.join(HERE, "upcoming_matches.json")
SQUADS_FILE = os.path.join(HERE, "upcoming_squads.json")

FORMAT_MAP = {"t20": "T20", "t20i": "T20", "odi": "ODI", "test": "TEST"}

BLOCKED_SERIES = [
    "t20 blast", "royal london", "sheffield shield", "marsh cup", "plunket",
    "county championship", "big bash", "super smash", "premier cup",
    "three-day", "two-day", "four-day", "csa ", "provincial",
    "domestic", "trophy", "premier league", "t10", "ecs ", "ecl",
    "kncu", "club", "schools", "warm-up", "tour match",
]


def _get(path: str, params: dict, timeout: int = 25) -> dict:
    r = requests.get(f"{BASE}/{path}", params={"apikey": API_KEY, **params}, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    if d.get("status") != "success":
        raise RuntimeError(f"cricapi error on /{path}: {d.get('reason')}")
    return d


def _blocked(name: str) -> bool:
    text = (name or "").lower()
    return any(b in text for b in BLOCKED_SERIES)


def _map_match(m: dict) -> dict | None:
    fmt = FORMAT_MAP.get((m.get("matchType") or "").lower())
    if not fmt:
        return None
    teams = m.get("teams") or []
    if len(teams) != 2 or any((t or "").upper() in ("TBC", "") for t in teams):
        return None
    if _blocked(m.get("series") or m.get("name") or ""):
        return None
    return {
        "match_id": m.get("id"),
        "series_id": m.get("series_id"),
        "series": m.get("series") or "",
        "team1": teams[0],
        "team2": teams[1],
        "match_type": fmt,
        "venue": m.get("venue") or "Venue TBC",
        "date": m.get("date"),
        "datetime_gmt": m.get("dateTimeGMT"),
        "status": "Upcoming" if not m.get("matchStarted") else m.get("status", ""),
        "fantasy_enabled": bool(m.get("fantasyEnabled", True)),
        "has_squad": bool(m.get("hasSquad", False)),
        "match_started": bool(m.get("matchStarted", False)),
        "match_ended": bool(m.get("matchEnded", False)),
    }


def fetch_imminent(days: int) -> list:
    """Live-or-imminent international fixtures from currentMatches (1 API hit)."""
    d = _get("currentMatches", {"offset": 0})
    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=days)

    mapped, seen = [], set()
    for m in d.get("data") or []:
        try:
            mdate = m.get("date")
            if not mdate:
                continue
            date = datetime.strptime(mdate, "%Y-%m-%d").date()
            if not (today <= date <= end) or m.get("matchEnded"):
                continue
            row = _map_match(m)
            if not row or row["match_id"] in seen:
                continue
            seen.add(row["match_id"])
            mapped.append(row)
        except (ValueError, TypeError):
            continue
    mapped.sort(key=lambda x: (x["date"], str(x["match_id"])))
    return mapped


def fetch_squad(match_id: str) -> dict | None:
    d = _get("matchSquad", {"matchid": match_id})
    squads = d.get("data") or []
    if not squads:
        return None

    def role_map(raw) -> str | None:
        if not raw:
            return None
        r = str(raw).lower()
        if "wick" in r:
            return "WK"
        if "bowl" in r:
            return "BOWL"
        if "all" in r:
            return "AR"
        if "bat" in r:
            return "BAT"
        return None

    available = []
    for block in squads:
        players = [
            {
                "player_id": str(p.get("id", "")),
                "player_name": (p.get("name") or "").strip(),
                "role": role_map(p.get("role")),
                "is_confirmed": True,
                "injury_status": "UNKNOWN",
                "squad_source": "cricapi",
            }
            for p in (block.get("players") or [])
            if (p.get("name") or "").strip()
        ]
        if players:
            available.append({"team_name": block.get("teamName") or "", "players": players})
    return {"match_id": match_id, "available_squads": available} if available else None


def main():
    parser = argparse.ArgumentParser(description="Imminent-fixture sync via cricketdata.org")
    parser.add_argument("--days", type=int, default=2, help="Imminent window from today (default 2)")
    parser.add_argument("--try-squads", action="store_true", help="Attempt squad fetch (plan-locked on free tier)")
    args = parser.parse_args()

    if not API_KEY:
        raise SystemExit("CRICKET_DATA_API_KEY missing from .env")

    print("Fetching imminent fixtures via currentMatches (cricapi free tier)...")
    matches = fetch_imminent(args.days)
    for m in matches:
        print(f"    {m['date']}  {m['match_type']:4s}  {m['team1']} vs {m['team2']}")
    print(f"  imminent international fixtures: {len(matches)}")

    try:
        with open(MATCHES_FILE, "r", encoding="utf-8") as f:
            old = json.load(f).get("matches", [])
    except FileNotFoundError:
        old = []
    new_ids = {str(m["match_id"]) for m in matches}
    # Replace old entries that are now started/ended; keep prior upcoming feed entries
    merged = matches + [
        m for m in old
        if str(m.get("match_id")) not in new_ids and not m.get("match_started")
    ]

    payload = {
        "fetched_at": datetime.now().isoformat(),
        "source": "cricketdata.org (cricapi free tier)",
        "match_count": len(merged),
        "matches": merged,
    }
    with open(MATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[OK] wrote {len(merged)} matches -> {MATCHES_FILE}")

    if args.try_squads and matches:
        try:
            with open(SQUADS_FILE, "r", encoding="utf-8") as f:
                squads = json.load(f).get("squads", {})
        except FileNotFoundError:
            squads = {}

        plan_locked = False
        for m in matches:
            if not m.get("has_squad"):
                continue
            mid = str(m["match_id"])
            try:
                entry = fetch_squad(mid)
            except RuntimeError as e:
                if "Invalid API" in str(e) and not plan_locked:
                    print("  [NOTE] matchSquad is plan-locked on the free tier —")
                    print("         squads require RAPID_API_KEY (schedule_fetcher.py).")
                    plan_locked = True
                continue
            if entry:
                entry["team1"] = m["team1"]
                entry["team2"] = m["team2"]
                squads[mid] = entry
            time.sleep(0.5)

        if not plan_locked:
            with open(SQUADS_FILE, "w", encoding="utf-8") as f:
                json.dump({"fetched_at": datetime.now().isoformat(), "squads": squads}, f, indent=2, ensure_ascii=False)
            print(f"[OK] squads available for {len(squads)} matches")


if __name__ == "__main__":
    main()
