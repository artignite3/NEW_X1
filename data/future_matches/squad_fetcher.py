"""Quota-bounded squad refresh; provider failures preserve verified entries."""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.future_matches.fixture_store import load as load_matches
from data.future_matches.squad_store import load as load_squads, publish

load_dotenv()
SERIES_SQUAD_CACHE = {}
PLAYER_CACHE = {}
_REQUESTS = 0
_MAX_REQUESTS = 3


class RequestBudgetExceeded(RuntimeError):
    pass


def fetch(endpoint):
    global _REQUESTS
    if _REQUESTS >= _MAX_REQUESTS:
        raise RequestBudgetExceeded("Squad request budget reached; existing squads retained")
    _REQUESTS += 1
    key = os.getenv("RAPID_API_KEY")
    if not key:
        raise ValueError("RAPID_API_KEY is not configured")
    response = requests.get(f"https://cricbuzz-cricket.p.rapidapi.com/{endpoint}", timeout=20,
        headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"})
    response.raise_for_status()
    return response.json()


def get_series_squads(series_id):
    if series_id not in SERIES_SQUAD_CACHE:
        SERIES_SQUAD_CACHE[series_id] = fetch(f"series/v1/{series_id}/squads")
    return SERIES_SQUAD_CACHE[series_id]


def get_squad_players(series_id, squad_id):
    key = (str(series_id), str(squad_id))
    if key not in PLAYER_CACHE:
        PLAYER_CACHE[key] = fetch(f"series/v1/{series_id}/squads/{squad_id}")
    return PLAYER_CACHE[key]


def normalize_role(role):
    role = str(role).lower()
    if "wk" in role or "keeper" in role: return "WK"
    if "allround" in role: return "AR"
    if "bowl" in role: return "BOWL"
    return "BAT"


def refresh_match(match, existing):
    from model.team_generator import _teams_match, has_usable_match_squads
    series = match.get("series_id")
    if not series:
        return None
    data = get_series_squads(series)
    blocks = []
    for block in data.get("squads", []):
        label = block.get("squadType", "")
        if block.get("isHeader") or not block.get("squadId"):
            continue
        if not any(_teams_match(label, team) for team in (match["team1"], match["team2"])):
            continue
        response = get_squad_players(series, block["squadId"])
        players = [{"player_id": str(p.get("id", "")), "player_name": p.get("name", ""),
                    "role": normalize_role(p.get("role", "")), "batting_style": p.get("battingStyle", ""),
                    "bowling_style": p.get("bowlingStyle", ""), "injury_status": "UNKNOWN",
                    "squad_source": "cricbuzz", "is_confirmed": False}
                   for p in response.get("player", []) if not p.get("isHeader") and p.get("name")]
        blocks.append({"team_name": label, "team_id": block.get("teamId"), "players": players})
    entry = {"match_id": match["match_id"], "series_id": series, "series": match.get("series", ""),
             "team1": match["team1"], "team2": match["team2"], "format": match["match_type"],
             "fetched_at": datetime.now(timezone.utc).isoformat(), "available_squads": blocks}
    return entry if has_usable_match_squads(match, entry) else None


def main():
    global _REQUESTS, _MAX_REQUESTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default="")
    parser.add_argument("--max-requests", type=int, default=3)
    args = parser.parse_args()
    if args.max_requests < 1: raise SystemExit("Request budget must be positive")
    _REQUESTS, _MAX_REQUESTS = 0, args.max_requests
    matches = load_matches()["matches"]
    if not matches: raise SystemExit("No verified upcoming fixtures")
    selected = set(filter(None, (i.strip() for i in args.ids.split(","))))
    prior = load_squads()
    output = {"squads": dict(prior["squads"]), "fetched_at": prior["fetched_at"]}
    incomplete = False
    changed = False
    for match in sorted(matches, key=lambda m: m["date"]):
        identity = str(match["match_id"])
        if selected and identity not in selected: continue
        try:
            entry = refresh_match(match, output["squads"].get(identity))
            if entry:
                output["squads"][identity] = entry
                output["fetched_at"] = datetime.now(timezone.utc).isoformat()
                changed = True
            else:
                incomplete = True
        except RequestBudgetExceeded:
            incomplete = True
            print("[WARN] Squad request budget reached; remaining entries retained")
            break
        except (requests.RequestException, ValueError, TypeError, KeyError):
            incomplete = True
            print(f"[WARN] Squad provider unavailable for {identity}; existing entry retained")
    if changed: publish(output)
    print(f"Squad refresh: {_REQUESTS} provider calls, {len(output['squads'])} retained match entries")
    if incomplete: raise SystemExit(3)


if __name__ == "__main__": main()
