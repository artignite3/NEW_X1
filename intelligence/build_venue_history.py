"""Build the small checked-in venue snapshot from local Cricsheet archives.

Run: python -m intelligence.build_venue_history --raw-dir data/raw
Raw archives are never required by the serving API.
"""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from collections import defaultdict
from pathlib import Path

from data_processing.safe_publish import promote
from intelligence.venue_history import FORMAT_MAP, SNAPSHOT_NAME, ground_key, make_snapshot, validate_snapshot
from project_paths import data_root

ARCHIVES = {"t20": ("t20s_json.zip", "T20_data.csv"),
            "odi": ("odis_json.zip", "ODI_ODM_data.csv"),
            "test": ("tests_json.zip", "Test_MDM_data.csv")}
BOWLER_WICKETS = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}


def style_kind(label: str) -> str | None:
    label = (label or "").lower()
    if any(token in label for token in ("spin", "break", "orthodox", "chinaman")):
        return "spin"
    if any(token in label for token in ("pace", "fast", "medium")):
        return "pace"
    return None


def read_styles(path: Path) -> dict:
    styles = {}
    if not path.is_file():
        return styles
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row.get("Innings Type") != "Bowling" or row.get("Super Over") == "True":
                continue
            kind = style_kind(row.get("Bowler Type", ""))
            if not kind:
                continue
            key = (row["Date"], ground_key(row["Venue"]), row["Player"])
            if key in styles and styles[key] != kind:
                styles[key] = None  # Ambiguous names never become style evidence.
            elif key not in styles:
                styles[key] = kind
    return styles


def _phase(fmt: str, over: int) -> str:
    if fmt == "t20":
        return "powerplay" if over < 6 else "death" if over >= 15 else "middle"
    if fmt == "odi":
        return "powerplay" if over < 10 else "death" if over >= 40 else "middle"
    return "early" if over < 30 else "late" if over >= 80 else "middle"


def match_record(data: dict, match_id: str, styles: dict) -> dict | None:
    info = data.get("info", {})
    fmt = FORMAT_MAP.get(str(info.get("match_type", "")).lower())
    venue, dates = info.get("venue"), info.get("dates")
    if not fmt or not venue or not dates or info.get("missing") or info.get("outcome", {}).get("method"):
        return None
    innings = [i for i in data.get("innings", []) if not i.get("super_over")]
    if not innings or any(i.get("super_over") for i in data.get("innings", [])):
        return None
    match_date = min(dates)
    available_date = max(dates)
    first = None
    style = defaultdict(lambda: {"pace": [0, 0, 0], "spin": [0, 0, 0]})
    for innings_number, item in enumerate(innings):
        runs = balls = wickets = boundaries = 0
        for over in item.get("overs", []):
            phase = _phase(fmt, int(over["over"]))
            for delivery in over.get("deliveries", []):
                extras = delivery.get("extras", {})
                charged = int(delivery["runs"]["total"]) - sum(int(extras.get(k, 0)) for k in ("byes", "legbyes", "penalty"))
                legal = not extras.get("wides") and not extras.get("noballs")
                dismissals = delivery.get("wickets", [])
                bowler_wickets = sum(w["kind"] in BOWLER_WICKETS for w in dismissals)
                if innings_number == 0:
                    runs += int(delivery["runs"]["total"])
                    balls += int(legal)
                    wickets += sum(w["kind"] not in ("retired hurt", "retired out") for w in dismissals)
                    boundaries += int(delivery["runs"]["batter"] in (4, 6) and not delivery["runs"].get("non_boundary"))
                kind = styles.get((match_date, ground_key(venue), delivery["bowler"]))
                if kind:
                    bucket = style[phase][kind]
                    bucket[0] += charged
                    bucket[1] += int(legal)
                    bucket[2] += bowler_wickets
        if innings_number == 0:
            minimum = {"t20": 96, "odi": 240, "test": 120}[fmt]
            if balls >= minimum or wickets == 10:
                first = {"runs": runs, "balls": balls, "wickets": wickets, "boundaries": boundaries}
    if first is None:
        return None
    winner = info.get("outcome", {}).get("winner")
    defended = (winner == innings[0].get("team")) if fmt in ("t20", "odi") and len(innings) >= 2 and winner in info.get("teams", []) else None
    return {"id": match_id, "date": match_date, "available_date": available_date,
            "venue": venue, "format": fmt,
            "gender": info.get("gender", "unknown"), "team_type": info.get("team_type", "unknown"),
            "first": first, "style": dict(style), "defended": defended}


def build(raw_dir: Path, destination: Path) -> dict:
    matches = []
    previous_style = {}
    if destination.is_file():
        try:
            with destination.open(encoding="utf-8") as handle:
                previous = validate_snapshot(json.load(handle))
            previous_style = {m["id"]: m["style"] for m in previous["matches"]}
        except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
            pass
    for fmt, (archive_name, csv_name) in ARCHIVES.items():
        styles = read_styles(raw_dir / csv_name)
        with zipfile.ZipFile(raw_dir / archive_name) as archive:
            for member in archive.namelist():
                if not member.endswith(".json"):
                    continue
                record = match_record(json.loads(archive.read(member)), f"{fmt}:{Path(member).stem}", styles)
                if record is not None:
                    if not styles and not record["style"] and record["id"] in previous_style:
                        record["style"] = previous_style[record["id"]]
                    matches.append(record)
    snapshot = make_snapshot(matches)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    def check(path):
        with Path(path).open(encoding="utf-8") as handle:
            validate_snapshot(json.load(handle))
    promote(temporary, destination, validate=check)
    return {"matches": len(matches), "venues": len({ground_key(m["venue"]) for m in matches}), "snapshot": str(destination)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=data_root() / "raw")
    parser.add_argument("--output", type=Path, default=data_root() / SNAPSHOT_NAME)
    args = parser.parse_args()
    print(json.dumps(build(args.raw_dir, args.output)))
