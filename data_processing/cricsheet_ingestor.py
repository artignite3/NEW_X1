"""Read Cricsheet ZIP members directly and incrementally score completed matches.

No career aggregates are copied into match records. Per-innings batting,
bowling and fielding statistics are counted directly from deliveries.
"""
import hashlib
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from project_paths import data_root
from data_processing.safe_publish import promote
from model.calculator_t20 import calculate_fantasy_points_t20
from model.calculate_odi import calculate_fantasy_points_odi
from model.calculator_test import calculate_fantasy_points_test

INGESTION_VERSION = 2
CALCULATORS = {"t20": calculate_fantasy_points_t20, "odi": calculate_fantasy_points_odi, "test": calculate_fantasy_points_test}
ARCHIVES = {"t20": "t20s", "odi": "odis", "test": "tests"}


def atomic_json(path, value, *, preserve_current=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    promote(temporary, path, preserve_current=preserve_current)


def match_records(match, source_id, fmt):
    info = match["info"]
    start, end = min(info["dates"]), max(info["dates"])
    teams = info["teams"]
    match_key = f"{teams[0]}-{teams[1]}-{start}-{info.get('gender', 'unknown')}-{info['match_type']}-{source_id}"
    stats = {}
    for team, names in info["players"].items():
        for name in names:
            s = {"Total Runs Scored": 0, "Fours": 0, "Sixes": 0, "Balls Faced": 0,
                 "Wickets": 0, "Bowled": 0, "LBW": 0, "Bowls Bowled": 0,
                 "Runs Given": 0, "Catches Taken": 0, "Stumped Outs Made": 0,
                 "Run Outs Made": 0, "Maiden Overs": 0, "Dot Balls": 0,
                 "Team Name": team, "Opposition Team": next(t for t in teams if t != team)}
            for i in range(1, 5):
                s.update({f"Innings {i} Runs": 0, f"Innings {i} Wickets": 0,
                          f"Innings {i} Balls Faced": 0, f"How Out Inning {i} (Not Played)": 1,
                          f"How Out Inning {i} (not out)": 1})
            stats[name] = s

    for i, innings in enumerate(match["innings"], 1):
        if innings.get("super_over"):
            continue
        for over in innings.get("overs", []):
            conceded, legal_by_bowler = {}, {}
            for ball in over["deliveries"]:
                batter, bowler = ball["batter"], ball["bowler"]
                for n in (batter, bowler, ball.get("non_striker")):
                    if n and n not in stats:
                        raise ValueError(f"Player {n} absent from registered match squad")
                bat, bowl = stats[batter], stats[bowler]
                extras, runs = ball.get("extras", {}), ball["runs"]
                bat[f"How Out Inning {i} (Not Played)"] = 0
                if ball.get("non_striker"):
                    stats[ball["non_striker"]][f"How Out Inning {i} (Not Played)"] = 0
                bat["Total Runs Scored"] += runs["batter"]
                bat[f"Innings {i} Runs"] += runs["batter"]
                bat["Fours"] += int(runs["batter"] == 4 and not runs.get("non_boundary"))
                bat["Sixes"] += int(runs["batter"] == 6 and not runs.get("non_boundary"))
                if not extras.get("wides"):
                    bat["Balls Faced"] += 1
                    bat[f"Innings {i} Balls Faced"] += 1
                legal = not extras.get("wides") and not extras.get("noballs")
                bowl["Bowls Bowled"] += int(legal)
                legal_by_bowler[bowler] = legal_by_bowler.get(bowler, 0) + int(legal)
                charged = runs["total"] - extras.get("byes", 0) - extras.get("legbyes", 0) - extras.get("penalty", 0)
                bowl["Runs Given"] += charged
                conceded[bowler] = conceded.get(bowler, 0) + charged
                bowl["Dot Balls"] += int(legal and runs["total"] == 0)
                for wicket in ball.get("wickets", []):
                    kind, out = wicket["kind"], wicket["player_out"]
                    if kind not in ("retired hurt", "obstructing the field", "retired out", "run out"):
                        bowl["Wickets"] += 1
                        bowl[f"Innings {i} Wickets"] += 1
                    bowl["Bowled"] += int(kind == "bowled")
                    bowl["LBW"] += int(kind == "lbw")
                    if out in stats and kind != "retired hurt":
                        stats[out][f"How Out Inning {i} (not out)"] = 0
                    if kind == "caught and bowled":
                        bowl["Catches Taken"] += 1
                    for fielder in wicket.get("fielders", []):
                        name = fielder.get("name")
                        if name not in stats:
                            continue
                        field = {"caught": "Catches Taken", "stumped": "Stumped Outs Made", "run out": "Run Outs Made"}.get(kind)
                        if field:
                            stats[name][field] += 1
            for bowler, balls in legal_by_bowler.items():
                if balls == info.get("balls_per_over", 6) and conceded.get(bowler, 0) == 0:
                    stats[bowler]["Maiden Overs"] += 1

    records = {}
    for player, s in stats.items():
        batting_innings = sum(not s[f"How Out Inning {i} (Not Played)"] for i in range(1, 5))
        overs = s["Bowls Bowled"] / info.get("balls_per_over", 6)
        sr = s["Total Runs Scored"] * 100 / s["Balls Faced"] if s["Balls Faced"] else 0
        economy = s["Runs Given"] / overs if overs else 0
        s.update({"Overs Bowled": overs, "Avg Batting S/R Per Inning": sr, "Avg Economy Rate per inning": economy})
        points = CALCULATORS[fmt](s)
        records[player] = {
            **points, "team": s["Team Name"], "gender": info.get("gender"),
            "venue": info.get("venue", "Unknown"), "opponent": s["Opposition Team"],
            "match_date": start, "available_date": end, "source_id": source_id,
            "total_runs": s["Total Runs Scored"], "avg_runs_per_inning": s["Total Runs Scored"] / max(1, batting_innings),
            "boundaries": s["Fours"] + s["Sixes"], "fours": s["Fours"], "sixes": s["Sixes"],
            "wickets": s["Wickets"], "catches_taken": s["Catches Taken"],
            "stumped_outs_made": s["Stumped Outs Made"], "run_outs_made": s["Run Outs Made"],
            "balls_faced": s["Balls Faced"], "avg_balls_faced_per_inning": s["Balls Faced"] / max(1, batting_innings),
            "avg_batting_sr_per_inning": sr, "overs_bowled": overs, "bowls_bowled": s["Bowls Bowled"],
            "avg_economy_rate_per_inning": economy, "runs_given": s["Runs Given"],
            "runs_given_ball_per_inning": s["Runs Given"] / max(1, s["Bowls Bowled"]),
            "average_consecutive_dot_balls": 0, "batting_sr_aa": 0,
        }
    return match_key, records


def ingest_format(fmt):
    processed = data_root() / "processed"
    output = processed / f"player_fantasy_points_{fmt}.json"
    manifest_path = processed / f"ingestion_{fmt}.json"
    existing_valid = True
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        compatible = manifest.get("version") == INGESTION_VERSION and output.exists()
        data = json.loads(output.read_text(encoding="utf-8")) if compatible else {}
        if compatible and (not isinstance(data, dict) or not data):
            raise ValueError("Invalid existing fantasy history")
        existing_valid = compatible
    except (OSError, ValueError, TypeError):
        print(f"[WARN] {fmt}: damaged primary history or manifest; rebuilding from archive", flush=True)
        existing_valid = False
        manifest, compatible, data = {}, False, {}
    previous = manifest.get("members", {}) if compatible else {}
    members = {}
    updated = 0
    with zipfile.ZipFile(data_root() / "raw" / f"{ARCHIVES[fmt]}_json.zip") as archive:
        for item in archive.infolist():
            if not item.filename.endswith(".json"):
                continue
            fingerprint = f"{item.CRC}:{item.file_size}"
            if previous.get(item.filename) == fingerprint:
                members[item.filename] = fingerprint
                continue
            match = json.loads(archive.read(item))
            if min(match["info"]["dates"]) < "2010-01-01" or max(match["info"]["dates"]) >= date.today().isoformat():
                continue
            source_id = Path(item.filename).stem
            key, records = match_records(match, source_id, fmt)
            # A corrected archive member replaces every old player record for it.
            if item.filename in previous:
                for history in data.values():
                    for old_key in list(history):
                        if history[old_key].get("source_id") == source_id:
                            del history[old_key]
            for player, stats in records.items():
                data.setdefault(player, {})[key] = stats
            members[item.filename] = fingerprint
            updated += 1
    if updated or not compatible:
        atomic_json(output, data, preserve_current=existing_valid)
    atomic_json(manifest_path, {"version": INGESTION_VERSION, "members": members, "latest_available_date": max((s["available_date"] for h in data.values() for s in h.values()), default=None)}, preserve_current=existing_valid)
    print(f"{fmt}: {updated} added/changed matches; {len(data)} players", flush=True)


def run_pipeline():
    for fmt in ARCHIVES:
        ingest_format(fmt)


if __name__ == "__main__":
    run_pipeline()
