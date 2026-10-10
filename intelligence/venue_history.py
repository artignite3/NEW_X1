"""Auditable, date-safe venue history derived from Cricsheet deliveries.

The report describes past scoring; it does not claim to measure today's strip.
Historical evidence never changes fantasy-point multipliers without a separate
backtest. The compact snapshot is checked in so serving needs no raw archives.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

from project_paths import PROJECT_ROOT, data_root

SCHEMA = 3
SNAPSHOT_NAME = "venue_history.json"
FORMAT_MAP = {"t20": "t20", "it20": "t20", "odi": "odi", "odm": "odi", "test": "test", "mdm": "test"}
MIN_BASELINE_MATCHES = 20
MIN_REPORT_MATCHES = 5
MIN_STYLE_BALLS = 120
ALIASES = {
    "chepauk": "ma chidambaram stadium",
    "feroz shah kotla": "arun jaitley stadium",
}


def ground_key(name: str) -> str:
    key = re.sub(r"\s+", " ", (name or "").split(",")[0].strip().lower())
    return ALIASES.get(key, key)


def city_key(name: str) -> str:
    parts = (name or "").split(",")
    return re.sub(r"\s+", " ", parts[-1].strip().lower()) if len(parts) > 1 else ""


def _digest(matches: list[dict]) -> str:
    raw = json.dumps(matches, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ValueError("Venue history schema mismatch")
    matches = snapshot.get("matches")
    if not isinstance(matches, list) or not matches or _digest(matches) != snapshot.get("sha256"):
        raise ValueError("Venue history checksum mismatch")
    seen = set()
    for match in matches:
        if not isinstance(match, dict) or not {"id", "date", "available_date", "venue", "format", "gender", "team_type", "first", "style", "defended"}.issubset(match):
            raise ValueError("Incomplete venue match")
        if match["id"] in seen or match["format"] not in ("t20", "odi", "test"):
            raise ValueError("Duplicate or invalid venue match")
        seen.add(match["id"])
        if not all(isinstance(match[field], str) and match[field].strip() for field in ("id", "venue", "gender", "team_type")):
            raise ValueError("Missing venue match identity")
        if date.fromisoformat(match["available_date"]) < date.fromisoformat(match["date"]):
            raise ValueError("Venue match available before it started")
        first = match["first"]
        if first is not None:
            if not isinstance(first, dict) or any(type(first.get(k)) is not int or first[k] < 0 for k in ("runs", "balls", "wickets", "boundaries")) or first["balls"] == 0:
                raise ValueError("Invalid first innings")
        if not isinstance(match["style"], dict):
            raise ValueError("Invalid bowling style evidence")
        if match["defended"] is not None and type(match["defended"]) is not bool:
            raise ValueError("Invalid defended outcome")
        for kinds in match["style"].values():
            if not isinstance(kinds, dict) or set(kinds) - {"pace", "spin"}:
                raise ValueError("Invalid bowling style class")
            for values in kinds.values():
                if not isinstance(values, list) or len(values) != 3 or any(type(v) is not int or v < 0 for v in values):
                    raise ValueError("Invalid bowling style counts")
    return snapshot


def make_snapshot(matches: list[dict]) -> dict:
    matches = sorted(matches, key=lambda m: (m["available_date"], m["id"]))
    return validate_snapshot({"schema": SCHEMA, "source": "Cricsheet JSON", "matches": matches, "sha256": _digest(matches)})


def _read_snapshot(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return validate_snapshot(json.load(handle))


@lru_cache(maxsize=8)
def _load_at(path: str, mtime_ns: int) -> dict:
    return _read_snapshot(Path(path))


def load_snapshot() -> tuple[dict | None, str]:
    """Try current, last-good, then packaged snapshot; never serve corrupt data."""
    live = data_root() / SNAPSHOT_NAME
    packaged = PROJECT_ROOT / "data" / SNAPSHOT_NAME
    candidates = [live, live.with_name(live.name + ".last_good"), packaged,
                  packaged.with_name(packaged.name + ".last_good")]
    for path in dict.fromkeys(candidates):
        try:
            return _load_at(str(path), path.stat().st_mtime_ns), str(path)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            continue
    return None, "unavailable"


def _identity(matches: list[dict], venue: str) -> list[dict]:
    """Match only exact normalized ground names; disambiguate city collisions."""
    ground = ground_key(venue)
    if not ground:
        return []
    group = [m for m in matches if ground_key(m["venue"]) == ground]
    cities = {city_key(m["venue"]) for m in group if city_key(m["venue"])}
    requested_city = city_key(venue)
    if len(cities) > 1:
        return [m for m in group if requested_city and city_key(m["venue"]) == requested_city]
    if requested_city and cities and requested_city not in cities:
        return []
    return group


def _summary(matches: list[dict], fmt: str) -> dict:
    first = [m["first"] for m in matches if m["first"] is not None]
    same_format = [m["first"] for m in matches if m["format"] == fmt and m["first"] is not None]
    balls = sum(i["balls"] for i in same_format)
    return {
        "matches": len(first),
        "same_format_matches": len(same_format),
        "avg_1st_innings": round(sum(i["runs"] for i in same_format) / len(same_format), 1) if same_format else None,
        "wickets_per_innings": round(sum(i["wickets"] for i in same_format) / len(same_format), 1) if same_format else None,
        "defended": sum(m["defended"] is True for m in matches),
        "decided_limited_overs": sum(m["defended"] is not None for m in matches),
        "runs_per_over": round(6 * sum(i["runs"] for i in same_format) / balls, 2) if balls else None,
        "boundary_pct": round(100 * sum(i["boundaries"] for i in same_format) / balls, 1) if balls else None,
        "from_date": matches[0]["date"] if matches else None,
        "to_date": matches[-1]["available_date"] if matches else None,
    }


def _baseline(matches: list[dict], target: dict) -> tuple[float, float, float] | None:
    # A match is compared with its own format, gender and team level. Limit the
    # baseline to the preceding five years so old T20 scoring is not modern T20.
    year = int(target["date"][:4])
    peers = [m["first"] for m in matches if m["first"] is not None
             and m["available_date"] < target["date"] and int(m["available_date"][:4]) >= year - 5
             and (m["format"], m["gender"], m["team_type"]) ==
             (target["format"], target["gender"], target["team_type"])]
    if len(peers) < MIN_BASELINE_MATCHES:
        return None
    balls = sum(i["balls"] for i in peers)
    return (sum(i["runs"] for i in peers) / balls,
            sum(i["wickets"] for i in peers) / balls,
            sum(i["runs"] for i in peers) / len(peers))


def _style_bias(venue_matches: list[dict], world: list[dict]) -> tuple[str, dict]:
    # Compare bowling styles within phase and format, never raw overall economy.
    evidence = defaultdict(lambda: [0, 0, 0])
    baseline = defaultdict(lambda: [0, 0, 0])
    venue_ids = {m["id"] for m in venue_matches}
    classes = {(m["format"], m["gender"], m["team_type"]) for m in venue_matches}
    for m in world:
        if (m["format"], m["gender"], m["team_type"]) not in classes:
            continue
        for phase, styles in m["style"].items():
            for kind in ("pace", "spin"):
                values = styles.get(kind, [0, 0, 0])
                key = (m["format"], m["gender"], m["team_type"], phase, kind)
                dest = baseline[key]
                for n in range(3): dest[n] += values[n]
                if m["id"] in venue_ids:
                    dest = evidence[key]
                    for n in range(3): dest[n] += values[n]
    totals = Counter()
    effects = defaultdict(list)
    for key, (runs, balls, wickets) in evidence.items():
        bruns, bballs, bwickets = baseline[key]
        kind = key[-1]
        totals[kind] += balls
        if balls >= 18 and bballs >= 300 and bruns and bwickets:
            # More wickets and fewer runs is better for bowlers; both are
            # normalized to their format and phase peer group.
            effect = 0.5 * ((wickets / balls) / (bwickets / bballs)) + 0.5 * ((bruns / bballs) / (runs / balls)) if runs else 0
            if effect: effects[kind].append((effect, balls))
    detail = {kind: {"balls": totals[kind]} for kind in ("pace", "spin")}
    if any(totals[kind] < MIN_STYLE_BALLS or not effects[kind] for kind in ("pace", "spin")):
        return "INSUFFICIENT EVIDENCE", detail
    scores = {kind: sum(v * w for v, w in effects[kind]) / sum(w for _, w in effects[kind]) for kind in ("pace", "spin")}
    if scores["spin"] > scores["pace"] * 1.12:
        return "SPIN FAVOURING", detail
    if scores["pace"] > scores["spin"] * 1.12:
        return "PACE FAVOURING", detail
    return "BALANCED", detail


def report(venue: str, fmt: str, as_of: str, gender: str = "male", team_type: str | None = None) -> dict | None:
    try:
        cutoff_date = date.fromisoformat(as_of)
        cutoff = cutoff_date.isoformat()
    except (TypeError, ValueError):
        return None
    snapshot, path = load_snapshot()
    if snapshot is None:
        return None
    world = [m for m in snapshot["matches"] if m["available_date"] < cutoff and m["gender"] == gender
             and (team_type is None or m["team_type"] == team_type)]
    identity = {m["id"] for m in _identity(snapshot["matches"], venue)}
    matches = [m for m in world if m["id"] in identity and m["first"] is not None
               and (cutoff_date - date.fromisoformat(m["available_date"])).days <= 5 * 366]
    matches.sort(key=lambda m: (m["available_date"], m["id"]))
    if not matches or (cutoff_date - date.fromisoformat(matches[-1]["available_date"])).days > 3 * 366:
        return None
    window10 = matches[-10:]
    qualified = [(m, _baseline(world, m)) for m in window10]
    qualified = [(m, b) for m, b in qualified if b is not None]
    if len(qualified) < MIN_REPORT_MATCHES:
        return None
    # Ratio to the contemporaneous peer baseline makes cross-format evidence
    # comparable without mixing raw T20, ODI and Test innings totals.
    ratios = [((m["first"]["runs"] / m["first"]["balls"]) / b[0],
               (m["first"]["wickets"] / m["first"]["balls"]) / b[1] if b[1] else 1)
              for m, b in qualified]
    scoring = sum(x[0] for x in ratios) / len(ratios)
    wickets = sum(x[1] for x in ratios) / len(ratios)
    low_defences = {m["id"] for m, b in qualified if m["defended"] is True and m["first"]["runs"] <= 0.9 * b[2]}
    recent_scoring = sum(x[0] for x in ratios[-5:]) / min(5, len(ratios))
    if scoring >= 1.10 and recent_scoring >= 1.05:
        category = "BATTING"
    elif scoring <= 0.90 and recent_scoring <= 0.95:
        category = "BOWLING"
    else:
        category = "NEUTRAL"
    bias, style = _style_bias(window10, world)
    return {
        "source": "historical", "format": fmt, "sample_size": len(qualified),
        "category": category, "bowling_bias": bias,
        "confidence": "moderate" if len(qualified) >= 10 else "low",
        "last5": {**_summary(window10[-5:], fmt), "low_total_defences": sum(m["id"] in low_defences for m in window10[-5:])},
        "last10": {**_summary(window10, fmt), "low_total_defences": len(low_defences)},
        "match_ids": [m["id"] for m in window10],
        "scoring_vs_peers_pct": round((scoring - 1) * 100, 1),
        "wickets_vs_peers_pct": round((wickets - 1) * 100, 1),
        "style_evidence": style, "as_of": cutoff,
        "snapshot_latest_match": snapshot["matches"][-1]["available_date"],
        "snapshot_fallback": path.endswith(".last_good"),
        "batter_mult": 1.0, "pacer_mult": 1.0, "spinner_mult": 1.0,
        "avg_1st_innings": _summary(window10, fmt)["avg_1st_innings"],
        "boundary_pct": _summary(window10, fmt)["boundary_pct"],
        "description": f"Recent venue scoring was {abs(round((scoring - 1) * 100))}% {'above' if scoring >= 1 else 'below'} comparable matches. Historical tendency, not a match-day pitch assessment; team scores remain neutral.",
    }
