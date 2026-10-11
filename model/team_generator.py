"""
NEW_X1 — Team Generation Core
Orchestrates the full prediction & optimization pipeline for a match:

  1. Player pool assembly (fixture squads or custom simulator teams)
  2. Name resolution: Cricbuzz display names -> Cricsheet fantasy keys
  3. Predictions: TriBE ensemble / CatBoost over precomputed rolling features
     (anti-leakage: only feature rows with match_date <= requested date)
  4. Statistical layer: recent-form mean & variance from fantasy points,
     league prior for players without history
  5. Intelligence layer: venue pitch PAF, live weather, injury multipliers
  6. PuLP optimization: risk-adjusted XI with role & team diversity constraints
  7. Explainability cache for the /explain_team endpoint (SHAP + Ollama)

Anti-leakage guarantee: every lookups' history and features are strictly
filtered to dates BEFORE the requested match date.
"""

import hashlib
import uuid
import json
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pulp

from model.name_resolver import PlayerNameResolver
from model.predict_model import predict_squad
from intelligence.pitch_analyzer import get_venue_profile, pitch_multiplier
from intelligence.venue_registry import canonical_venue
from intelligence.weather_fetcher import fetch_venue_weather, weather_multiplier

BASE = Path(__file__).resolve().parent.parent
from project_paths import data_root
DATA_PROCESSED = data_root() / "processed"
FUTURE_MATCHES = data_root() / "future_matches"

# ── Caches (process-level, warmed on first use per format) ───────────────────
_FANTASY_CACHE: Dict[str, dict] = {}
_DATA_STAMPS: dict = {}
_FANTASY_SOURCES: dict = {}
_RESOLVER_CACHE: Dict[str, PlayerNameResolver] = {}
_PRIOR_CACHE: Dict[str, dict] = {}          # fmt -> {"prior": float, "prior_var": float}
_SQUADS_JSON: Optional[dict] = None
_MATCHES_JSON: Optional[dict] = None
_DATEWISE_JSON: Optional[dict] = None
_DATEWISE_STAMP: object = None
_DATEWISE_SOURCE: str = "unavailable"
_DATEWISE_INDEX: Optional[dict] = None      # normalized team -> [(date, players, fmt)]

# Explainability cache: generation responses keep their feature rows here so
# /explain_team can compute SHAP without re-loading parquet. LRU, capped.
_EXPLAIN_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_EXPLAIN_CACHE_MAX = 32

NUM_HISTORY_MATCHES = 65
CI_Z_SCORE = 1.28          # Historical spread heuristic; coverage is uncalibrated
CAPTAIN_VARIANCE_WEIGHT = 0.30

INJURY_MULTIPLIERS = {
    "FIT": 1.00, "UNKNOWN": 1.00, "DOUBTFUL": 0.45,
    "INJURED": 0.05, "RESTED": 0.00, "SUSPENDED": 0.00,
}
PLAYING_PROB_ADJUSTMENTS = {
    "FIT": 1.10, "UNKNOWN": 1.00, "DOUBTFUL": 0.40,
    "INJURED": 0.00, "RESTED": 0.00, "SUSPENDED": 0.00,
}
# NOTE: UNKNOWN is treated as "no information" (multiplier 1.0), not as a
# 10% penalty — Cricbuzz marks almost every player UNKNOWN by default.

ROLE_MAP = {
    "WK": "WK", "WICKETKEEPER": "WK", "WICKET-KEEPER": "WK",
    "BAT": "BAT", "BATTER": "BAT", "BATSMENT": "BAT",
    "BOWL": "BOWL", "BOWLER": "BOWL",
    "AR": "AR", "ALL": "AR", "ALLROUNDER": "AR", "ALL-ROUNDER": "AR", "ALL ROUNDER": "AR",
}


# ─────────────────────────────────────────────────────────────────────────────
# Data access (cached)
# ─────────────────────────────────────────────────────────────────────────────
def normalize_format(fmt: str) -> str:
    f = (fmt or "").strip().lower()
    if f in ("t20", "t20i", "itt20"):
        return "t20"
    if f in ("odi", "odm", "one day", "one-day"):
        return "odi"
    if f in ("test", "mdm", "test cricket"):
        return "test"
    raise ValueError(f"Invalid format '{fmt}'. Must be T20, ODI or Test.")


def validate_date(date: str) -> str:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise ValueError("Date must be in YYYY-MM-DD format")
    return date


def get_fantasy(fmt: str) -> dict:
    from data_processing.safe_publish import last_good
    path = DATA_PROCESSED / f"player_fantasy_points_{fmt}.json"
    backup = last_good(path)
    stamp = tuple((p.stat().st_mtime_ns, p.stat().st_ctime_ns, p.stat().st_size)
                  if p.exists() else None for p in (path, backup))
    if fmt not in _FANTASY_CACHE or _DATA_STAMPS.get(fmt) != stamp:
        errors = []
        for source, candidate in (("current", path), ("last_good", backup)):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not data:
                    raise ValueError("Fantasy history is empty or malformed")
                _FANTASY_CACHE[fmt] = data
                _FANTASY_SOURCES[fmt] = source
                for other in list(_FANTASY_CACHE):
                    if other != fmt:
                        _FANTASY_CACHE.pop(other, None)
                        _DATA_STAMPS.pop(other, None)
                _RESOLVER_CACHE.pop(fmt, None)
                _PRIOR_CACHE.clear()
                _DATA_STAMPS[fmt] = stamp
                break
            except (OSError, ValueError, TypeError) as error:
                errors.append(f"{candidate.name}: {type(error).__name__}")
        else:
            raise FileNotFoundError(f"No valid {fmt} fantasy history ({'; '.join(errors)})")
    return _FANTASY_CACHE[fmt]


def get_resolver(fmt: str) -> PlayerNameResolver:
    get_fantasy(fmt)
    if fmt not in _RESOLVER_CACHE:
        _RESOLVER_CACHE[fmt] = PlayerNameResolver(get_fantasy(fmt))
    return _RESOLVER_CACHE[fmt]


def get_squads_json() -> dict:
    from data.future_matches.squad_store import load
    return load()["squads"]


def get_matches_json() -> list:
    from data.future_matches.fixture_store import load
    return load()["matches"]


def get_datewise_json() -> dict:
    global _DATEWISE_JSON, _DATEWISE_STAMP, _DATEWISE_SOURCE
    from data_processing.safe_publish import last_good
    primary = DATA_PROCESSED / "datewise_squad.json"
    backup = last_good(primary)
    stamp = tuple((p.stat().st_mtime_ns, p.stat().st_ctime_ns, p.stat().st_size)
                  if p.exists() else None for p in (primary, backup))
    if _DATEWISE_JSON is None or _DATEWISE_STAMP != stamp:
        errors = []
        for source, candidate in (("current", primary), ("last_good", backup)):
            try:
                value = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(value, dict) or not value:
                    raise ValueError("Squad history is malformed")
                _DATEWISE_JSON = value
                _DATEWISE_SOURCE = source
                _DATEWISE_STAMP = stamp
                break
            except (OSError, ValueError, TypeError) as error:
                errors.append(f"{candidate.name}: {type(error).__name__}")
        else:
            raise FileNotFoundError("No valid datewise squad history: " + "; ".join(errors))
    return _DATEWISE_JSON


def get_league_prior(fmt: str, match_date: str) -> Tuple[float, float]:
    """
    Empirical prior for players without history: the median player's recent
    mean points and the median variance across the format's population.
    """
    cache_key = (fmt, match_date)
    if cache_key in _PRIOR_CACHE:
        return _PRIOR_CACHE[cache_key]["prior"], _PRIOR_CACHE[cache_key]["prior_var"]

    fantasy = get_fantasy(fmt)
    means, variances = [], []
    for key in fantasy:
        matches = player_history(fantasy, key, match_date, n=30)
        if len(matches) < 10:
            continue
        recent = [
            float(m.get("total_points") or 0)
            for m in matches
        ]
        if recent:
            means.append(float(np.mean(recent)))
            if len(recent) > 1:
                variances.append(float(np.var(recent)))

    prior = float(np.median(means)) if means else 15.0
    prior_var = float(np.median(variances)) if variances else 400.0
    _PRIOR_CACHE[cache_key] = {"prior": prior, "prior_var": prior_var}
    return prior, prior_var


# ─────────────────────────────────────────────────────────────────────────────
# Player pool assembly
# ─────────────────────────────────────────────────────────────────────────────
def _norm_team(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (label or "").lower()).strip()


# Generic tokens that must not drive team matching ("India Squad" ~ "India",
# but "India Women" must not match "India" in a men's fixture)
_TEAM_STOP_TOKENS = {"squad", "xi", "one", "off", "test", "odi", "t20", "t20i", "second"}


def _team_tokens(label: str) -> set:
    return {
        t for t in _norm_team(label).split()
        if t and t not in _TEAM_STOP_TOKENS
    }


def _teams_match(a: str, b: str) -> bool:
    """Token-overlap team matching, robust to 'Hong Kong, China' vs 'Hong Kong Squad'."""
    ta, tb = _team_tokens(a), _team_tokens(b)
    if not ta or not tb:
        return False
    if ("women" in ta) != ("women" in tb):
        return False
    overlap = ta & tb
    if not overlap:
        return False
    return ta <= tb or tb <= ta or len(overlap) >= min(len(ta), len(tb))


def _map_role(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return ROLE_MAP.get(str(raw).strip().upper())


def _pick_squad_for_team(available_squads: List[dict], team: str, fmt: str) -> Optional[dict]:
    """Chooses the right squad block for a team, preferring format-matching ones."""
    candidates = [s for s in available_squads if _teams_match(s.get("team_name", ""), team)]
    if not candidates:
        return None

    def score(s: dict) -> tuple:
        name = s.get("team_name", "").lower()
        fmt_kw = {"t20": "t20", "odi": "odi", "test": "test"}[fmt]
        fmt_match = 1 if fmt_kw in name else 0
        n_players = len(s.get("players", []))
        confirmed = sum(1 for p in s.get("players", []) if p.get("is_confirmed"))
        return (fmt_match, confirmed, n_players)

    return max(candidates, key=score)


def has_usable_match_squads(match: dict, entry: dict) -> bool:
    """Availability means both fixture teams have enough distinct named players."""
    if not isinstance(entry, dict):
        return False
    team1, team2 = match.get("team1"), match.get("team2")
    if not team1 or not team2:
        return False
    try:
        fmt = normalize_format(match.get("match_type", entry.get("format", "t20")))
    except ValueError:
        return False
    blocks = entry.get("available_squads")
    if isinstance(blocks, list):
        if any(not isinstance(block, dict) for block in blocks):
            return False
        picked = [_pick_squad_for_team(blocks, team, fmt) for team in (team1, team2)]
        lists = [(block or {}).get("players", []) for block in picked]
    else:
        lists = [(entry.get(key) or {}).get("players", []) if isinstance(entry.get(key), dict) else []
                 for key in ("team1", "team2")]
    names = []
    for players in lists:
        if not isinstance(players, list):
            return False
        names.append({(p.get("player_name") or p.get("name") or "").strip() if isinstance(p, dict)
                      else str(p).strip() for p in players} - {""})
    return all(names) and len(names[0] | names[1]) >= 11


def get_match_info(match_id) -> Optional[dict]:
    for m in get_matches_json():
        if str(m.get("match_id")) == str(match_id):
            return m
    return None


def _fantasy_history_stamp(fmt: str) -> tuple:
    from data_processing.safe_publish import last_good
    primary = DATA_PROCESSED / f"player_fantasy_points_{fmt}.json"
    return tuple((path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None
                 for path in (primary, last_good(primary)))


@lru_cache(maxsize=3)
def _historical_team_index(fmt: str, stamp: tuple) -> dict:
    """Completed match XIs by team and gender; rebuilt when fantasy data changes."""
    grouped: dict = {}
    for player, matches in get_fantasy(fmt).items():
        for match_key, stats in matches.items():
            day = stats.get("match_date")
            available = stats.get("available_date", day)
            team = stats.get("team")
            gender = stats.get("gender")
            if not all(isinstance(value, str) and value for value in (day, available, team, gender)):
                continue
            team_key = (gender, _norm_team(team).removesuffix(" women"))
            fixture_key = (day, str(stats.get("source_id") or match_key))
            grouped.setdefault(team_key, {}).setdefault(fixture_key, []).append((player, available))
    return {team: sorted(fixtures.items(), reverse=True)
            for team, fixtures in grouped.items()}


def last_completed_team_squad(team: str, fmt: str, match_date: str) -> Optional[dict]:
    """Latest complete XI that was available before the requested fixture."""
    gender = "female" if "women" in team.lower() else "male"
    team_key = (gender, _norm_team(team).removesuffix(" women"))
    for (day, _source_id), players in _historical_team_index(fmt, _fantasy_history_stamp(fmt)).get(team_key, []):
        if day >= match_date:
            continue
        names = sorted({name for name, available in players if available < match_date})
        if len(names) >= 11:
            return {"date": day, "players": names}
    return None


def last_match_squads_for_fixture(match: dict, fmt: str) -> Optional[dict]:
    """A provisional two-team pool, never presented as a confirmed squad."""
    date = validate_date(match["date"])
    first = last_completed_team_squad(match["team1"], fmt, date)
    second = last_completed_team_squad(match["team2"], fmt, date)
    if not first or not second or set(first["players"]) & set(second["players"]):
        return None
    return {"team1": first, "team2": second}


def pool_from_match_squads(match_id, fmt: str) -> Tuple[List[dict], dict]:
    """
    Builds the player pool from Cricbuzz squads for an upcoming fixture.
    Handles both stored schemas:
      - available_squads: [{team_name, players: [...]}, ...]
      - direct:           {team1: {team_name, players}, team2: {...}}
    """
    squads_json = get_squads_json()
    entry = squads_json.get(str(match_id), {})
    match = get_match_info(match_id) or entry
    if not match:
        raise ValueError(f"Match {match_id} not found")
    team1, team2 = match.get("team1") or entry.get("team1"), match.get("team2") or entry.get("team2")
    team1_label = team1.get("team_name") if isinstance(team1, dict) else team1
    team2_label = team2.get("team_name") if isinstance(team2, dict) else team2
    venue = match.get("venue", "")
    date = match.get("date", "")
    fmt = normalize_format(fmt or match.get("match_type", "t20"))

    if not has_usable_match_squads(match, entry):
        historical = last_match_squads_for_fixture(match, fmt)
        if not historical:
            raise ValueError(f"No verified or complete same-format historical squads for match {match_id}")
        pool = []
        squads_out = {"team1_name": team1_label, "team2_name": team2_label,
                      "team1": [], "team2": []}
        for key, label in (("team1", team1_label), ("team2", team2_label)):
            for name in historical[key]["players"]:
                player = {"display_name": name, "role": None, "team": label,
                          "injury_status": "UNKNOWN", "source": "last_completed_match",
                          "bowling_style": ""}
                pool.append(player)
                squads_out[key].append(player)
        return pool, {"match": match, "venue": venue, "date": date,
                      "squads": squads_out, "squad_source": "last_match",
                      "squad_match_dates": {team1_label: historical["team1"]["date"],
                                            team2_label: historical["team2"]["date"]}}

    # Flatten the two schemas into per-team player lists
    per_team: Dict[str, List[dict]] = {team1_label: [], team2_label: []}
    if isinstance(entry.get("available_squads"), list):
        for team_label in (team1_label, team2_label):
            block = _pick_squad_for_team(entry["available_squads"], team_label, fmt)
            per_team[team_label] = (block or {}).get("players", [])
    else:
        for team_label, key in ((team1_label, "team1"), (team2_label, "team2")):
            node = entry.get(key)
            if isinstance(node, dict):
                per_team[team_label] = node.get("players", [])

    pool = []
    squads_out = {"team1_name": team1_label, "team2_name": team2_label, "team1": [], "team2": []}
    for team_label, key in ((team1_label, "team1"), (team2_label, "team2")):
        seen = set()
        for p in per_team[team_label]:
            name = (p.get("player_name") or p.get("name") or "").strip() if isinstance(p, dict) else str(p).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            player = {
                "display_name": name,
                "role": _map_role(p.get("role")) if isinstance(p, dict) else None,
                "team": team_label,
                "injury_status": (p.get("injury_status") or "UNKNOWN").upper() if isinstance(p, dict) else "UNKNOWN",
                "source": "cricbuzz_squad",
                "bowling_style": p.get("bowling_style", "") if isinstance(p, dict) else "",
            }
            pool.append(player)
            squads_out[key].append(player)

    if len(pool) < 2:
        raise ValueError(
            f"Squad data for match {match_id} is incomplete ({len(pool)} players). "
            "Re-run data/future_matches/squad_fetcher.py to refresh squads."
        )
    return pool, {"match": match, "venue": venue, "date": date,
                  "squads": squads_out, "squad_source": "provider"}


def _build_datewise_index() -> dict:
    """Reverse index: normalized team name -> [(date, [players], format)] newest-first."""
    global _DATEWISE_INDEX
    if _DATEWISE_INDEX is not None:
        return _DATEWISE_INDEX
    index: Dict[str, List[tuple]] = {}
    for date, leagues in sorted(get_datewise_json().items(), reverse=True):
        for _league, fixtures in leagues.items():
            for _fixture_key, info in fixtures.items():
                fmt = normalize_format(info.get("Format", "t20"))
                for field, players in info.items():
                    if field == "Format" or not isinstance(players, list):
                        continue
                    team_name = field.replace("_Second_Squad", "")
                    index.setdefault(_norm_team(team_name), []).append((date, players, fmt))
    _DATEWISE_INDEX = index
    return index


def pool_from_custom_teams(team1: str, team2: str, fmt: str, match_date: str) -> List[dict]:
    """Use each team's latest completed squad of the requested gender/format."""
    fantasy = get_fantasy(fmt)
    pool = []
    for label in (team1, team2):
        gender = "female" if "women" in label.lower() else "male"
        normalized = _norm_team(label).replace(" women", "")
        latest_date, names = "", set()
        for name, matches in fantasy.items():
            for match_key, stats in matches.items():
                actual_team = stats.get("team")
                day = stats.get("match_date")
                available = stats.get("available_date", day)
                if not day or not available or available >= match_date:
                    continue
                if stats.get("gender") != gender or _norm_team(actual_team or "") != normalized:
                    continue
                if day > latest_date:
                    latest_date, names = day, {name}
                elif day == latest_date:
                    names.add(name)
        if not names:
            raise ValueError(f"No completed {fmt.upper()} squad for '{label}' before {match_date}")
        pool.extend({"display_name": n, "role": None, "team": label,
                     "injury_status": "UNKNOWN", "source": "latest_completed_squad"} for n in sorted(names))
    seen, unique = set(), []
    for player in pool:
        if player["display_name"] not in seen:
            seen.add(player["display_name"])
            unique.append(player)
    return unique


def infer_role_from_history(history: List[dict]) -> str:
    """Fallback role inference from the batting/bowling points split."""
    if not history:
        return "BAT"
    if any(float(m.get("stumped_outs_made") or 0) > 0 for m in history):
        return "WK"
    bat = float(np.mean([m.get("batting_points") or 0 for m in history]))
    bowl = float(np.mean([m.get("bowling_points") or 0 for m in history]))
    if bat >= 10 and bowl >= 10:
        return "AR"
    if bowl > bat:
        return "BOWL"
    return "BAT"


# ─────────────────────────────────────────────────────────────────────────────
# History & covariance
# ─────────────────────────────────────────────────────────────────────────────
def player_history(fantasy: dict, key: str, date: str, n: int = NUM_HISTORY_MATCHES) -> List[dict]:
    """Player's match stats strictly BEFORE the match date (anti-leakage), newest last."""
    if not key:
        return []
    raw = fantasy.get(key)
    if not raw:
        return []
    try:
        cutoff = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return []
    rows = []
    for match_key, stats in raw.items():
        m = re.search(r"(\d{4}-\d{2}-\d{2})", match_key)
        if not m:
            continue
        if datetime.strptime(stats.get("available_date", m.group(1)), "%Y-%m-%d") < cutoff:
            rows.append((m.group(1), stats))
    rows.sort(key=lambda x: x[0])
    return [s for _d, s in rows[-n:]]


def build_covariance_matrix(histories: Dict[str, List[float]],
                            players: List[str],
                            variances: Dict[str, float]) -> pd.DataFrame:
    """
    Covariance of fantasy points across the squad. Sequences are padded to a
    common length with each player's own mean (zero covariance contribution),
    then the diagonal is overridden with true per-player variances.
    """
    # Match IDs align shared observations. Missing matches contribute zero
    # residual, rather than pairing unrelated nth-most-recent games.
    aligned = pd.DataFrame({p: pd.Series(histories.get(p, {}), dtype=float) for p in players})
    vectors = []
    for p in players:
        observed = aligned[p]
        residual = (observed - observed.mean()).fillna(0).to_numpy()
        norm = np.linalg.norm(residual)
        vectors.append(residual * np.sqrt(max(0, variances.get(p, 0))) / norm if norm else np.zeros(len(residual)))
    matrix = np.column_stack(vectors) if vectors else np.zeros((0, 0))
    arr = matrix.T @ matrix
    for i, p in enumerate(players):
        arr[i, i] = max(arr[i, i], variances.get(p, 0))
    return pd.DataFrame(arr, index=players, columns=players)


# ─────────────────────────────────────────────────────────────────────────────
# Optimizer (same constraint structure as heuristic_solver, with status control)
# ─────────────────────────────────────────────────────────────────────────────
def solve_xi(stats_df: pd.DataFrame,
             cov_matrix: pd.DataFrame,
             risk_aversion: float = 0.05,
             max_players: int = 11,
             use_role_bounds: bool = True,
             use_team_bounds: bool = True) -> Tuple[List[str], str]:
    """
    Maximizes sum(mu) - lambda * sum(var) over binary selection.
    Role bounds: 1<=WK<=5, 1<=BAT<=6, 2<=BOWL<=5, AR<=5.
    Team bounds: 1..7 per side. Returns (selected_players, solver_status).
    """
    n = len(stats_df)
    players = stats_df["player"].tolist()
    mu = stats_df["mean_points"].values
    var = np.diag(cov_matrix.values) if len(cov_matrix) == n else stats_df["variance"].values

    roles = stats_df.get("role", pd.Series(["BAT"] * n, name="role")).tolist()
    teams = stats_df["team"].tolist() if "team" in stats_df.columns else None

    lp = pulp.LpProblem("NEW_X1_Optimization", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)}
    objective = pulp.lpSum((mu[i] - risk_aversion * var[i]) * x[i] for i in range(n))

    # Pairwise covariance terms (correlation-aware risk). Kept only for pairs
    # whose covariance is meaningful: sub-threshold pairs are estimation noise
    # from <=65 aligned samples. Cap at 40 strongest interactions; every kept
    # pair costs one binary plus three constraints. Dense CBC models can hang
    # well past their reported 10-second limit on real 50-player pools.
    COV_PRUNE_RATIO = 0.10
    MAX_PAIR_TERMS = 40
    candidate_pairs = (
        [(abs(float(cov_matrix.iloc[i, j])), i, j) for i in range(n) for j in range(i + 1, n)]
        if risk_aversion and len(cov_matrix) == n else []
    )
    cov_cap = max((strength for strength, _, _ in candidate_pairs), default=0.0)
    kept_pairs = sorted((p for p in candidate_pairs if p[0] >= COV_PRUNE_RATIO * cov_cap),
                        reverse=True)[:MAX_PAIR_TERMS] if cov_cap else []
    for _, i, j in kept_pairs:
        covariance = float(cov_matrix.iloc[i, j])
        pair = pulp.LpVariable(f"pair_{i}_{j}", cat="Binary")
        lp += pair <= x[i]
        lp += pair <= x[j]
        lp += pair >= x[i] + x[j] - 1
        objective -= 2 * risk_aversion * covariance * pair
    lp += objective
    lp += pulp.lpSum(x[i] for i in range(n)) == max_players

    if use_role_bounds:
        def idx(prefixes):
            return [i for i, r in enumerate(roles) if str(r).upper() in prefixes]
        wk, bat = idx(("WK", "WICKETKEEPER")), idx(("BAT", "BATTER"))
        bowl, ar = idx(("BOWL", "BOWLER")), idx(("AR", "ALLROUNDER", "ALL-ROUNDER"))
        if not wk or not bat or len(bowl) < 2:
            return [], "Infeasible"
        if wk:
            lp += pulp.lpSum(x[i] for i in wk) >= 1
            lp += pulp.lpSum(x[i] for i in wk) <= 5
        if bat:
            lp += pulp.lpSum(x[i] for i in bat) >= 1
            lp += pulp.lpSum(x[i] for i in bat) <= 6
        if bowl:
            lp += pulp.lpSum(x[i] for i in bowl) >= 2
            lp += pulp.lpSum(x[i] for i in bowl) <= 5
        if ar:
            lp += pulp.lpSum(x[i] for i in ar) <= 5

    if use_team_bounds and teams:
        unique = set(teams)
        if len(unique) >= 2:
            for t in unique:
                t_idx = [i for i, tt in enumerate(teams) if tt == t]
                lp += pulp.lpSum(x[i] for i in t_idx) >= 1
                lp += pulp.lpSum(x[i] for i in t_idx) <= 7

    try:
        lp.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=10, threads=1, maxNodes=1000))
        status = pulp.LpStatus[lp.status]
    except pulp.PulpSolverError as e:
        print(f"[WARN] CBC solver failed: {e}")
        return [], "SolverError"
    selected = [players[i] for i in range(n) if (x[i].value() or 0) > 0.5] if status == "Optimal" else []
    return selected, status


# ─────────────────────────────────────────────────────────────────────────────
# Main generation pipeline
# ─────────────────────────────────────────────────────────────────────────────
def generate_best_team(payload: dict) -> dict:
    match_id = payload.get("match_id")
    team1 = payload.get("team1")
    team2 = payload.get("team2")

    raw_fmt = payload.get("format")
    if not raw_fmt and match_id:
        match = get_match_info(match_id)
        if match:
            raw_fmt = match.get("match_type", "t20")
    fmt = normalize_format(raw_fmt or "t20")

    use_ml = bool(payload.get("use_ml", True))
    requested_ml = use_ml
    model_failure = None
    use_intelligence = bool(payload.get("use_intelligence", True))
    scan_news = bool(payload.get("scan_news", False))
    risk_aversion = float(payload.get("risk_aversion", 0.05))
    if not np.isfinite(risk_aversion) or not 0 <= risk_aversion <= 0.2:
        raise ValueError("risk_aversion must be between 0 and 0.2")
    mode = payload.get("mode", "prediction")
    if mode not in ("prediction", "retrospective"):
        raise ValueError("mode must be prediction or retrospective")

    meta: dict = {}
    if match_id:
        pool, meta = pool_from_match_squads(match_id, fmt)
        date = validate_date(payload.get("date") or meta["date"])
        venue = canonical_venue(payload.get("venue") or meta["venue"] or "Neutral Venue")
        team1, team2 = meta["squads"]["team1_name"], meta["squads"]["team2_name"]
    else:
        if not team1 or not team2:
            raise ValueError("Provide either match_id, or team1 + team2 (Custom Simulator)")
        if _norm_team(team1) == _norm_team(team2):
            raise ValueError("The two teams must differ")
        date = validate_date(payload.get("date") or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
        pool = pool_from_custom_teams(team1, team2, fmt, date)
        venue = canonical_venue(payload.get("venue") or "Neutral Venue")

    today = datetime.now().strftime("%Y-%m-%d")
    if mode == "prediction" and date <= today:
        raise ValueError("Predictions require tomorrow or a later date; use retrospective mode for completed matches")
    if mode == "retrospective" and (date >= today or date <= "2025-06-30"):
        raise ValueError("Retrospective analysis must be between 2025-07-01 and yesterday")

    # ── Name resolution ──────────────────────────────────────────────────
    fantasy = get_fantasy(fmt)
    resolver = get_resolver(fmt)
    resolution_log = {"resolved": 0, "unresolved": []}
    seen_keys = set()
    deduped_pool = []
    for p in pool:
        key, method = resolver.resolve(p["display_name"], require_gender="female" if "women" in (p["team"] or "").lower() else "male")
        if key and key in seen_keys:
            continue  # duplicate person via two name variants
        if key:
            seen_keys.add(key)
            resolution_log["resolved"] += 1
        else:
            resolution_log["unresolved"].append(p["display_name"])
        p["fantasy_key"] = key
        p["name_match"] = method
        deduped_pool.append(p)
    pool = deduped_pool

    if len(pool) < 11:
        raise ValueError("At least 11 eligible players are required")

    # ── History stats ────────────────────────────────────────────────────
    for p in pool:
        hist = player_history(fantasy, p.get("fantasy_key"), date)
        p["history"] = hist
        p["matches_played"] = len(hist)
        if hist:
            p["stat_mean"] = float(np.mean([m.get("total_points") or 0 for m in hist]))
            p["stat_var"] = float(np.var([m.get("total_points") or 0 for m in hist]))
            if not p.get("role"):
                p["role"] = infer_role_from_history(hist)
                p["role_source"] = "inferred"
            else:
                p["role_source"] = "squad"
        else:
            p["stat_mean"] = None
            p["stat_var"] = None
            p["role"] = p.get("role") or "BAT"
            p["role_source"] = "default"

    # ── ML predictions (batched) ─────────────────────────────────────────
    details = None
    preds: Dict[str, float] = {}
    if use_ml:
        keys_with_history = [p["fantasy_key"] for p in pool if p["fantasy_key"] and p["matches_played"] > 0]
        if keys_with_history:
            try:
                pred_df, details = predict_squad(keys_with_history, fmt, date, return_details=True, venue=venue, opponents={p["fantasy_key"]: team2 if p["team"] == team1 else team1 for p in pool})
                preds = dict(zip(pred_df["player"], pred_df["predicted_score"]))
            except FileNotFoundError as e:
                print(f"[WARN] ML model unavailable for {fmt}: {e}")
                use_ml = False
                model_failure = str(e)
        else:
            use_ml = False
            model_failure = "No players have matching model history"

    prior, prior_var = get_league_prior(fmt, date)
    players_with_var = [p for p in pool if p["stat_var"] is not None]
    fallback_var = float(np.median([p["stat_var"] for p in players_with_var])) if players_with_var else prior_var

    # ── Intelligence layer ───────────────────────────────────────────────
    gender = "female" if "women" in f"{team1} {team2}".lower() else "male"
    pitch = get_venue_profile(venue, fmt, as_of=date, gender=gender) if use_intelligence else None
    weather = None
    intelligence_warnings = []
    if use_intelligence:
        weather = fetch_venue_weather(venue, date)
        if not weather or not weather.get("available", False):
            intelligence_warnings.append("Weather forecast unavailable; neutral weather adjustment used")

    news_reports: Dict[str, dict] = {}
    news_scan_used = False
    if scan_news:
        try:
            from intelligence.injury_detector import get_active_injury_reports
            news_reports = get_active_injury_reports([p["display_name"] for p in pool])
            news_scan_used = True
        except Exception as e:
            print(f"[WARN] Injury news scan failed: {e}")
            intelligence_warnings.append("Injury news scan unavailable; squad status only")

    # ── Scoring: base -> pitch PAF -> injury/availability ────────────────
    for p in pool:
        key = p.get("fantasy_key")
        if use_ml and key in preds:
            base = float(preds[key])
            p["engine"] = "ml"
        elif p["stat_mean"] is not None:
            base = p["stat_mean"]
            p["engine"] = "recent_form"
        else:
            base = prior
            p["engine"] = "league_prior"
        p["base_score"] = round(base, 2)

        style = p.get("bowling_style", "")
        p["pitch_multiplier"] = pitch_multiplier(p["role"], style, pitch) if pitch else 1.0
        p["weather_multiplier"] = weather_multiplier(p["role"], style, weather)

        status = p["injury_status"] if p["injury_status"] in INJURY_MULTIPLIERS else "UNKNOWN"
        news_hit = None
        for np_name, rep in news_reports.items():
            if np_name.lower() in p["display_name"].lower() or (
                key and np_name.lower() in key.lower()
            ):
                news_hit = rep
                break
        if news_hit:
            status = news_hit["status"]

        inj_mult = INJURY_MULTIPLIERS.get(status, 1.0)
        prob_adj = PLAYING_PROB_ADJUSTMENTS.get(status, 1.0)
        # These are availability scoring heuristics, not calibrated chances
        # of appearing in the XI. Squad membership does not confirm selection.
        if status == "DOUBTFUL":
            exp_factor = min(p["matches_played"] / 20.0, 1.0) if p["matches_played"] else 0.5
        else:
            exp_factor = 1.0
        playing_prob = min(prob_adj * exp_factor, 1.0)

        paf_score = base * p["pitch_multiplier"] * p["weather_multiplier"]
        final = paf_score * inj_mult * playing_prob

        p_std = float(np.sqrt(p["stat_var"] if p["stat_var"] is not None else fallback_var))
        p["injury_status"] = status
        p["injury_multiplier"] = inj_mult
        p["playing_probability"] = None
        p["availability_factor"] = round(playing_prob, 3)
        p["selection_status"] = "unconfirmed"
        p["adjusted_score"] = round(final, 2)
        p["variance"] = p["stat_var"] if p["stat_var"] is not None else fallback_var
        p["std"] = round(p_std, 2)
        p["ci_low"] = round(max(0.0, final - CI_Z_SCORE * p_std), 2)
        p["ci_high"] = round(final + CI_Z_SCORE * p_std, 2)
        p["captain_upside"] = round(final + CAPTAIN_VARIANCE_WEIGHT * p_std, 2)
        if news_hit:
            p["injury_news"] = news_hit.get("headline")

    # ── Covariance & optimization ────────────────────────────────────────
    pool_keys = [p["fantasy_key"] or f"__idx_{i}_{p['display_name']}" for i, p in enumerate(pool)]
    for p, k in zip(pool, pool_keys):
        if not p["fantasy_key"]:
            p["fantasy_key"] = k  # synthetic unique id for solver bookkeeping

    histories = {p["fantasy_key"]: {m.get("source_id", m.get("match_date", str(i))): float(m.get("total_points") or 0) for i, m in enumerate(p["history"])} for p in pool}
    variances = {p["fantasy_key"]: p["variance"] for p in pool}
    cov = build_covariance_matrix(histories, pool_keys, variances)

    stats_df = pd.DataFrame([{
        "player": p["fantasy_key"],
        "display_name": p["display_name"],
        "role": p["role"],
        "team": p["team"],
        "mean_points": p["adjusted_score"],
        "variance": p["variance"],
    } for p in pool])

    eligible = {p["fantasy_key"] for p in pool if p["injury_status"] not in {"INJURED", "RESTED", "SUSPENDED"}}
    stats_df = stats_df[stats_df.player.isin(eligible)].reset_index(drop=True)
    cov = cov.loc[stats_df.player, stats_df.player]

    # Strict by default: the full contract or a clear infeasibility. The
    # explicit allow_relaxation flag unlocks progressively weaker constraint
    # sets, and the response reports which one produced the XI.
    allow_relaxation = bool(payload.get("allow_relaxation", False))
    ladder = [("strict", True, True),
              ("relaxed_team", True, False),
              ("relaxed_roles", False, False)]
    selected_keys, status, constraint_mode = [], "Not Solved", "strict"
    for candidate_mode, use_role_bounds, use_team_bounds in ladder:
        if candidate_mode != "strict" and not allow_relaxation:
            break
        selected_keys, status = solve_xi(
            stats_df, cov, risk_aversion=risk_aversion,
            use_role_bounds=use_role_bounds, use_team_bounds=use_team_bounds)
        constraint_mode = candidate_mode
        if status == "Optimal" and len(selected_keys) == 11:
            break
    if status != "Optimal" or len(selected_keys) != 11:
        raise ValueError(
            "Cannot construct a valid XI: need 11 available players, a wicketkeeper, "
            "a batter, two bowlers and 1-7 players per team. Check squad roles and "
            "availability, or pass allow_relaxation=true to permit a relaxed selection."
        )

    selected_set = set(selected_keys)
    ordered = sorted(pool, key=lambda p: p["adjusted_score"], reverse=True)
    best_team = [p for p in ordered if p["fantasy_key"] in selected_set]
    bench = [p for p in ordered if p["fantasy_key"] not in selected_set]

    def entry(p: dict) -> dict:
        return {
            "display_name": p["display_name"],
            "fantasy_key": p["fantasy_key"],
            "role": p["role"],
            "role_source": p.get("role_source"),
            "team": p["team"],
            "engine": p["engine"],
            "base_score": p["base_score"],
            "pitch_multiplier": p["pitch_multiplier"],
            "weather_multiplier": p["weather_multiplier"],
            "bowling_style": p.get("bowling_style", ""),
            "injury_status": p["injury_status"],
            "injury_multiplier": p["injury_multiplier"],
            "playing_probability": p["playing_probability"],
            "availability_factor": p["availability_factor"],
            "selection_status": p["selection_status"],
            "adjusted_score": p["adjusted_score"],
            "std": p["std"],
            "ci_low": p["ci_low"],
            "ci_high": p["ci_high"],
            "uncertainty_method": "historical_spread_uncalibrated",
            "captain_upside": p["captain_upside"],
            "matches_played": p["matches_played"],
            "name_match": p.get("name_match"),
            "injury_news": p.get("injury_news"),
        }

    expected_total = round(sum(p["adjusted_score"] for p in best_team), 2)
    role_counts = {r: sum(1 for p in best_team if p["role"] == r) for r in ("WK", "BAT", "AR", "BOWL")}
    team_split = {}
    for p in best_team:
        team_split[p["team"]] = team_split.get(p["team"], 0) + 1

    # Captain recommendation: highest expected score with upside bonus
    captain = max(best_team, key=lambda p: p["captain_upside"])["display_name"] if best_team else None
    vice_captain = None
    if len(best_team) > 1:
        ranked = sorted(best_team, key=lambda p: p["captain_upside"], reverse=True)
        vice_captain = ranked[1]["display_name"]

    # Independent contract check (defense-in-depth; solver-independent)
    from model.squad_validator import validate_squad
    validation = validate_squad(
        [entry(p) for p in best_team], [entry(p) for p in pool],
        constraint_mode=constraint_mode, captain=captain, vice_captain=vice_captain,
    )
    if not validation["valid"]:
        raise ValueError("Squad contract violated: " + "; ".join(validation["violations"]))

    # ── Explainability cache ─────────────────────────────────────────────
    explain_token = uuid.uuid4().hex
    _EXPLAIN_CACHE[explain_token] = {
        "fmt": fmt,
        "date": date,
        "venue": venue,
        "details": details,
        "players": {p["fantasy_key"]: entry(p) for p in pool},
        "selected": [p["fantasy_key"] for p in best_team],
        "pitch_category": pitch.get("category") if pitch else "NEUTRAL",
        "constraint_mode": constraint_mode,
        "weather_summary": (weather or {}).get("summary", "Typical playing conditions"),
        "created": datetime.now().timestamp(),
    }
    while len(_EXPLAIN_CACHE) > _EXPLAIN_CACHE_MAX:
        _EXPLAIN_CACHE.popitem(last=False)

    intelligence = {
        "enabled": use_intelligence,
        "weather": weather,
        "pitch": pitch,
        "news_scan_used": news_scan_used,
    }

    from model.predict_model import _MODEL_SOURCES, _DF_SOURCES
    from data.future_matches.fixture_store import load as load_fixtures
    from data.future_matches.squad_store import load as load_squads
    model_used = bool(use_ml and details)
    fixtures = load_fixtures() if match_id else None
    squads = load_squads() if match_id else None
    data_provenance = {
        "model": _MODEL_SOURCES.get(fmt, "unavailable") if model_used else ("recent_form_fallback" if requested_ml and model_failure else "not_used"),
        "features": _DF_SOURCES.get(fmt, "unavailable") if model_used else "not_used",
        "fantasy": _FANTASY_SOURCES.get(fmt, "unavailable"),
        "fixtures": "last_good" if fixtures and fixtures["fallback_used"] else ("current" if fixtures else "not_used"),
        "squads": ("last_match" if meta.get("squad_source") == "last_match" else
                   "last_good" if squads and squads["fallback_used"] else
                   "current" if squads else "not_used"),
        "warnings": ([value["warning"] for value in (fixtures, squads) if value and value["warning"]]
                     + (["Projected player pool from the last completed same-format match: "
                         + ", ".join(f"{team} ({day})" for team, day in meta["squad_match_dates"].items())
                         + ". Current selection and availability are unconfirmed."]
                        if meta.get("squad_source") == "last_match" else [])
                     + (["No players have model history; using recent-form fallback" if model_failure.startswith("No players")
                         else "Saved ML model unavailable; using recent-form fallback"] if model_failure else [])
                     + intelligence_warnings),
    }

    return {
        "request": {
            "match_id": match_id, "team1": team1, "team2": team2,
            "format": fmt, "date": date, "venue": venue, "mode": mode,
            "use_ml": use_ml, "use_intelligence": use_intelligence,
            "risk_aversion": risk_aversion,
        },
        "best_team": [entry(p) for p in best_team],
        "bench": [entry(p) for p in bench],
        "data_provenance": data_provenance,
        "summary": {
            "expected_total_points": expected_total,
            "role_counts": role_counts,
            "team_split": team_split,
            "captain": captain,
            "vice_captain": vice_captain,
            "solver_status": status,
            "constraint_mode": constraint_mode,
            "squad_size": len(pool),
            "engine": ("CatBoost" if fmt == "t20" else "TriBE Ensemble (CatBoost+XGBoost+LightGBM)") if use_ml else "Recent Form (statistical)",
            "league_prior": round(prior, 2),
        },
        "intelligence": intelligence,
        "name_resolution": resolution_log,
        "validation": validation,
        "explain_token": explain_token,
    }
