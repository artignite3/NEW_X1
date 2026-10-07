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
import json
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pulp

from model.name_resolver import PlayerNameResolver
from model.predict_model import predict_squad
from intelligence.pitch_analyzer import get_venue_profile
from intelligence.weather_fetcher import fetch_venue_weather

BASE = Path(__file__).resolve().parent.parent
DATA_PROCESSED = BASE / "data" / "processed"
FUTURE_MATCHES = BASE / "data" / "future_matches"

# ── Caches (process-level, warmed on first use per format) ───────────────────
_FANTASY_CACHE: Dict[str, dict] = {}
_RESOLVER_CACHE: Dict[str, PlayerNameResolver] = {}
_PRIOR_CACHE: Dict[str, dict] = {}          # fmt -> {"prior": float, "prior_var": float}
_SQUADS_JSON: Optional[dict] = None
_MATCHES_JSON: Optional[dict] = None
_DATEWISE_JSON: Optional[dict] = None
_DATEWISE_INDEX: Optional[dict] = None      # normalized team -> [(date, players, fmt)]

# Explainability cache: generation responses keep their feature rows here so
# /explain_team can compute SHAP without re-loading parquet. LRU, capped.
_EXPLAIN_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_EXPLAIN_CACHE_MAX = 32

NUM_HISTORY_MATCHES = 65
CI_Z_SCORE = 1.28          # 80% confidence interval
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
    """Loads (and caches) the historical fantasy-points dictionary for a format."""
    if fmt not in _FANTASY_CACHE:
        path = DATA_PROCESSED / f"player_fantasy_points_{fmt}.json"
        with open(path, "r", encoding="utf-8") as f:
            _FANTASY_CACHE[fmt] = json.load(f)
    return _FANTASY_CACHE[fmt]


def get_resolver(fmt: str) -> PlayerNameResolver:
    if fmt not in _RESOLVER_CACHE:
        _RESOLVER_CACHE[fmt] = PlayerNameResolver(get_fantasy(fmt))
    return _RESOLVER_CACHE[fmt]


def get_squads_json() -> dict:
    global _SQUADS_JSON
    if _SQUADS_JSON is None:
        with open(FUTURE_MATCHES / "upcoming_squads.json", "r", encoding="utf-8") as f:
            _SQUADS_JSON = json.load(f).get("squads", {})
    return _SQUADS_JSON


def get_matches_json() -> list:
    global _MATCHES_JSON
    if _MATCHES_JSON is None:
        with open(FUTURE_MATCHES / "upcoming_matches.json", "r", encoding="utf-8") as f:
            _MATCHES_JSON = json.load(f).get("matches", [])
    return _MATCHES_JSON


def get_datewise_json() -> dict:
    global _DATEWISE_JSON
    if _DATEWISE_JSON is None:
        with open(DATA_PROCESSED / "datewise_squad.json", "r", encoding="utf-8") as f:
            _DATEWISE_JSON = json.load(f)
    return _DATEWISE_JSON


def get_league_prior(fmt: str) -> Tuple[float, float]:
    """
    Empirical prior for players without history: the median player's recent
    mean points and the median variance across the format's population.
    """
    if fmt in _PRIOR_CACHE:
        return _PRIOR_CACHE[fmt]["prior"], _PRIOR_CACHE[fmt]["prior_var"]

    fantasy = get_fantasy(fmt)
    means, variances = [], []
    for matches in fantasy.values():
        if len(matches) < 10:
            continue
        recent = [
            float(m.get("total_points") or 0)
            for m in list(matches.values())[-30:]
        ]
        if recent:
            means.append(float(np.mean(recent)))
            if len(recent) > 1:
                variances.append(float(np.var(recent)))

    prior = float(np.median(means)) if means else 15.0
    prior_var = float(np.median(variances)) if variances else 400.0
    _PRIOR_CACHE[fmt] = {"prior": prior, "prior_var": prior_var}
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


def get_match_info(match_id) -> Optional[dict]:
    for m in get_matches_json():
        if str(m.get("match_id")) == str(match_id):
            return m
    return None


def pool_from_match_squads(match_id, fmt: str) -> Tuple[List[dict], dict]:
    """
    Builds the player pool from Cricbuzz squads for an upcoming fixture.
    Handles both stored schemas:
      - available_squads: [{team_name, players: [...]}, ...]
      - direct:           {team1: {team_name, players}, team2: {...}}
    """
    squads_json = get_squads_json()
    entry = squads_json.get(str(match_id))
    if not entry:
        raise ValueError(f"No squad data available for match {match_id}")

    match = get_match_info(match_id) or entry
    team1, team2 = match.get("team1") or entry.get("team1"), match.get("team2") or entry.get("team2")
    team1_label = team1.get("team_name") if isinstance(team1, dict) else team1
    team2_label = team2.get("team_name") if isinstance(team2, dict) else team2
    venue = match.get("venue", "")
    date = match.get("date", "")
    fmt = normalize_format(fmt or match.get("match_type", "t20"))

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
            }
            pool.append(player)
            squads_out[key].append(player)

    if len(pool) < 2:
        raise ValueError(
            f"Squad data for match {match_id} is incomplete ({len(pool)} players). "
            "Re-run data/future_matches/squad_fetcher.py to refresh squads."
        )
    return pool, {"match": match, "venue": venue, "date": date, "squads": squads_out}


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


def pool_from_custom_teams(team1: str, team2: str, fmt: str) -> List[dict]:
    """
    Builds a pool for the Custom Simulator: the most relevant known squad for
    each team from the datewise squad dataset (names already Cricsheet-style).
    Squad blocks are scored by how many of their players have MALE match
    history — the dataset mixes men's and women's squads with no gender tag,
    and Cricbuzz-style fixtures default to the men's game.
    """
    index = _build_datewise_index()
    fantasy = get_fantasy(fmt)

    def male_histories(name: str) -> int:
        entry = fantasy.get(name)
        if not entry:
            return 0
        return sum(1 for k in entry if "-male-" in k)

    def block_score(players: List[str]) -> tuple:
        resolved = sum(1 for n in players if fantasy.get(n))
        male = sum(male_histories(n) for n in players)
        return (male, resolved, len(players))

    fmt = normalize_format(fmt)
    pool = []
    for team_label in (team1, team2):
        t_norm = _norm_team(team_label)
        entries = index.get(t_norm) or [
            (d, ps, f) for key, lst in index.items() for (d, ps, f) in lst if key in t_norm or t_norm in key
        ]
        if not entries:
            raise ValueError(f"No known squad for team '{team_label}'. Try a team listed at GET /teams.")
        fmt_filtered = [e for e in entries if e[2] == fmt] or entries
        best = max(fmt_filtered, key=lambda e: block_score(e[1]))
        _date, players, _f = best
        for name in players:
            pool.append({
                "display_name": name.strip(),
                "role": None,
                "team": team_label,
                "injury_status": "UNKNOWN",
                "source": "datewise_squad",
            })
    # Dedupe (same player can appear in both squads)
    seen = set()
    unique = []
    for p in pool:
        if p["display_name"].lower() in seen:
            continue
        seen.add(p["display_name"].lower())
        unique.append(p)
    return unique


def infer_role_from_history(history: List[dict]) -> str:
    """Fallback role inference from the batting/bowling points split."""
    if not history:
        return "BAT"
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
        if datetime.strptime(m.group(1), "%Y-%m-%d") < cutoff:
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
    max_len = max((len(h) for h in histories.values()), default=1)
    max_len = max(max_len, 2)
    data = {}
    for p in players:
        pts = [float(x) for x in histories.get(p, [])]
        if pts:
            mean = float(np.mean(pts))
            pts = pts + [mean] * (max_len - len(pts))
        else:
            pts = [0.0] * max_len
        data[p] = pts[-max_len:]

    df = pd.DataFrame(data)
    cov = df.cov().fillna(0.0)
    cov = (cov + cov.T) / 2

    arr = cov.values.copy()
    for i, p in enumerate(players):
        arr[i, i] = variances.get(p, 0.0)

    # Positive-semidefinite repair (numerical safety for the solver)
    min_eig = float(np.min(np.real(np.linalg.eigvals(arr))))
    if min_eig < 0:
        arr[np.diag_indices_from(arr)] += (-min_eig + 1e-8)

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
    lp += pulp.lpSum((mu[i] - risk_aversion * var[i]) * x[i] for i in range(n))
    lp += pulp.lpSum(x[i] for i in range(n)) == min(max_players, n)

    if use_role_bounds:
        def idx(prefixes):
            return [i for i, r in enumerate(roles) if str(r).upper() in prefixes]
        wk, bat = idx(("WK", "WICKETKEEPER")), idx(("BAT", "BATTER"))
        bowl, ar = idx(("BOWL", "BOWLER")), idx(("AR", "ALLROUNDER", "ALL-ROUNDER"))
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

    lp.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus[lp.status]
    selected = [players[i] for i in range(n) if (x[i].value() or 0) > 0.5]
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
    use_intelligence = bool(payload.get("use_intelligence", True))
    scan_news = bool(payload.get("scan_news", False))
    risk_aversion = float(payload.get("risk_aversion", 0.05))

    meta: dict = {}
    if match_id:
        pool, meta = pool_from_match_squads(match_id, fmt)
        date = validate_date(payload.get("date") or meta["date"])
        venue = payload.get("venue") or meta["venue"] or "Neutral Venue"
        team1, team2 = meta["squads"]["team1_name"], meta["squads"]["team2_name"]
    else:
        if not team1 or not team2:
            raise ValueError("Provide either match_id, or team1 + team2 (Custom Simulator)")
        pool = pool_from_custom_teams(team1, team2, fmt)
        date = validate_date(payload.get("date") or datetime.now().strftime("%Y-%m-%d"))
        venue = payload.get("venue") or "Neutral Venue"

    # ── Name resolution ──────────────────────────────────────────────────
    fantasy = get_fantasy(fmt)
    resolver = get_resolver(fmt)
    resolution_log = {"resolved": 0, "unresolved": []}
    seen_keys = set()
    deduped_pool = []
    for p in pool:
        key, method = resolver.resolve(p["display_name"])
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
        # Small pools can't field a constrained XI; still attempt best-available
        pass

    # ── History stats ────────────────────────────────────────────────────
    for p in pool:
        hist = player_history(fantasy, p.get("fantasy_key"), date)
        p["history"] = hist
        p["matches_played"] = len(hist)
        if hist:
            p["stat_mean"] = float(np.mean([m.get("total_points") or 0 for m in hist]))
            p["stat_var"] = float(np.var([m.get("total_points") or 0 for m in hist]))
            if not p.get("role"):
                p["role"] = infer_role_from_history(hist[-15:])
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
                pred_df, details = predict_squad(keys_with_history, fmt, date, return_details=True)
                preds = dict(zip(pred_df["player"], pred_df["predicted_score"]))
            except FileNotFoundError as e:
                print(f"[WARN] ML model unavailable for {fmt}: {e}")
                use_ml = False

    prior, prior_var = get_league_prior(fmt)
    players_with_var = [p for p in pool if p["stat_var"] is not None]
    fallback_var = float(np.median([p["stat_var"] for p in players_with_var])) if players_with_var else prior_var

    # ── Intelligence layer ───────────────────────────────────────────────
    pitch = get_venue_profile(venue, fmt) if use_intelligence else None
    weather = None
    if use_intelligence:
        weather = fetch_venue_weather(venue)

    news_reports: Dict[str, dict] = {}
    if scan_news:
        try:
            from intelligence.injury_detector import get_active_injury_reports
            news_reports = get_active_injury_reports()
        except Exception as e:
            print(f"[WARN] Injury news scan failed: {e}")

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

        if pitch is not None:
            p["pitch_multiplier"] = {
                "BAT": pitch.get("batter_mult", 1.0),
                "WK": pitch.get("batter_mult", 1.0),
                "BOWL": max(pitch.get("pacer_mult", 1.0), pitch.get("spinner_mult", 1.0)),
                "AR": (pitch.get("batter_mult", 1.0) + max(pitch.get("pacer_mult", 1.0), pitch.get("spinner_mult", 1.0))) / 2.0,
            }[p["role"]]
        else:
            p["pitch_multiplier"] = 1.0

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
        # Experience damping only applies when availability is genuinely in
        # doubt. A player named in an announced squad (FIT/UNKNOWN) is
        # expected to play — being uncapped is not an availability risk.
        if status == "DOUBTFUL":
            exp_factor = min(p["matches_played"] / 20.0, 1.0) if p["matches_played"] else 0.5
        else:
            exp_factor = 1.0
        playing_prob = min(prob_adj * exp_factor, 1.0)

        paf_score = base * p["pitch_multiplier"]
        final = paf_score * inj_mult * playing_prob

        p_std = float(np.sqrt(p["stat_var"] if p["stat_var"] is not None else fallback_var))
        p["injury_status"] = status
        p["injury_multiplier"] = inj_mult
        p["playing_probability"] = round(playing_prob * 100, 1)
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

    histories = {p["fantasy_key"]: [float(m.get("total_points") or 0) for m in p["history"]] for p in pool}
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

    selected_keys, status = solve_xi(stats_df, cov, risk_aversion=risk_aversion)
    if status != "Optimal":
        selected_keys, status = solve_xi(stats_df, cov, risk_aversion=risk_aversion, use_team_bounds=False)
    if status != "Optimal":
        selected_keys, status = solve_xi(stats_df, cov, risk_aversion=risk_aversion,
                                         use_role_bounds=False, use_team_bounds=False)
    if status != "Optimal":
        top = stats_df.nlargest(min(11, len(stats_df)), "mean_points")
        selected_keys, status = top["player"].tolist(), "GREEDY_FALLBACK"

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
            "injury_status": p["injury_status"],
            "injury_multiplier": p["injury_multiplier"],
            "playing_probability": p["playing_probability"],
            "adjusted_score": p["adjusted_score"],
            "std": p["std"],
            "ci_low": p["ci_low"],
            "ci_high": p["ci_high"],
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

    # ── Explainability cache ─────────────────────────────────────────────
    explain_token = hashlib.sha1(
        json.dumps([fmt, date, venue, sorted(pool_keys), use_ml, risk_aversion], default=str)
    .encode()).hexdigest()[:16]
    _EXPLAIN_CACHE[explain_token] = {
        "fmt": fmt,
        "date": date,
        "venue": venue,
        "details": details,
        "players": {p["fantasy_key"]: entry(p) for p in pool},
        "selected": [p["fantasy_key"] for p in best_team],
        "pitch_category": pitch.get("category") if pitch else "NEUTRAL",
        "weather_summary": (weather or {}).get("summary", "Typical playing conditions"),
        "created": datetime.now().timestamp(),
    }
    while len(_EXPLAIN_CACHE) > _EXPLAIN_CACHE_MAX:
        _EXPLAIN_CACHE.popitem(last=False)

    intelligence = {
        "enabled": use_intelligence,
        "weather": weather,
        "pitch": pitch,
        "news_scan_used": scan_news,
    }

    return {
        "request": {
            "match_id": match_id, "team1": team1, "team2": team2,
            "format": fmt, "date": date, "venue": venue,
            "use_ml": use_ml, "use_intelligence": use_intelligence,
            "risk_aversion": risk_aversion,
        },
        "best_team": [entry(p) for p in best_team],
        "bench": [entry(p) for p in bench],
        "summary": {
            "expected_total_points": expected_total,
            "role_counts": role_counts,
            "team_split": team_split,
            "captain": captain,
            "vice_captain": vice_captain,
            "solver_status": status,
            "squad_size": len(pool),
            "engine": "TriBE Ensemble (CatBoost+XGBoost+LightGBM)" if use_ml else "Recent Form (statistical)",
            "league_prior": round(prior, 2),
        },
        "intelligence": intelligence,
        "name_resolution": resolution_log,
        "explain_token": explain_token,
    }
