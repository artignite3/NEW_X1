"""
NEW_X1 — Feature Engineering (Vectorized — fast)
Transforms player_fantasy_points_*.json into ML-ready feature CSVs.

Uses pandas groupby + transform instead of per-player loops.
Output files in data/processed/:
  features_{fmt}.csv   — full feature matrix (all matches)
  train_{fmt}.csv      — matches <= 2025-06-30
  test_{fmt}.csv       — matches >  2025-06-30
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
from datetime import date, timedelta
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
DATA_PROCESSED = BASE / "data" / "processed"
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

FORMATS = {
    "t20":  DATA_PROCESSED / "player_fantasy_points_t20.json",
    "odi":  DATA_PROCESSED / "player_fantasy_points_odi.json",
    "test": DATA_PROCESSED / "player_fantasy_points_test.json",
}

TRAIN_CUTOFF = "2025-06-30"
FEATURE_SCHEMA_VERSION = 2


# Raw per-match numeric stats
RAW_STATS = [
    "total_runs", "avg_runs_per_inning", "boundaries", "sixes", "fours",
    "wickets", "catches_taken", "stumped_outs_made", "run_outs_made",
    "balls_faced", "avg_balls_faced_per_inning", "avg_batting_sr_per_inning",
    "overs_bowled", "bowls_bowled", "avg_economy_rate_per_inning",
    "average_consecutive_dot_balls", "runs_given", "runs_given_ball_per_inning",
    "batting_sr_aa", "batting_points", "bowling_points", "fielding_points",
]

# Career aggregate stats (stored inside each match record)
CAREER_STATS = [
    "Batting S/R", "Batting Avg", "Boundary %", "Runs/Ball",
    "Mean Score", "Scoring Consistency", "Dismissal Rate",
    "Economy Rate", "Bowling Avg", "Bowling S/R",
    "Dot Ball Bowled %", "Boundary Given %", "Win %",
]

LAG_WINDOWS  = [1, 2, 3]
ROLL_WINDOWS = [3, 7]
EMA_SPANS    = [3, 7]
DIFF_PERIODS = [1, 2, 3]

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def safe(v) -> float:
    try:
        f = float(v)
        return f if np.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0

def flatten_json(json_path: Path, fmt: str) -> pd.DataFrame:
    print(f"  Loading {json_path.name} ...", flush=True)
    with open(json_path) as f:
        data = json.load(f)

    rows = []
    for player, matches in tqdm(data.items(), desc=f"  Flatten {fmt}", ncols=80):
        for match_key, s in matches.items():
            m = DATE_RE.search(match_key)
            if not m:
                continue
            row = {
                "player":     player,
                "match_key":  match_key,
                "match_date": pd.Timestamp(m.group(1)),
                "available_date": pd.Timestamp(s.get("available_date", m.group(1))),
                "venue":      s.get("venue", "Unknown") or "Unknown",
                "opponent":   s.get("opponent", "Unknown") or "Unknown",
                "format":     fmt,
                "total_points": safe(s.get("total_points", 0)),
            }
            for col in RAW_STATS:
                row[col] = safe(s.get(col, 0))
            rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values(["player", "match_date"]).reset_index(drop=True)
    print(f"  Flattened: {len(df):,} rows x {len(df.columns)} cols")
    return df

def add_ts_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each player group add lag / rolling / EMA / diff / cumulative features.
    All features are computed on the SHIFTED series (shift=1) so match N
    only sees matches 1..N-1. No data leakage.
    """
    feature_cols = RAW_STATS + ["total_points"]
    df = df.sort_values(["player", "match_date", "match_key"]).reset_index(drop=True)
    group = df["player"]
    new_cols = {}
    for col in feature_cols:
        series = df[col].astype(float)
        grouped = series.groupby(group, sort=False)
        shifted = grouped.shift(1)
        shifted_group = shifted.groupby(group, sort=False)
        for lag in LAG_WINDOWS:
            new_cols[f"{col}_lag{lag}"] = grouped.shift(lag)
        for window in ROLL_WINDOWS:
            rolling = shifted_group.rolling(window, min_periods=1)
            new_cols[f"{col}_roll{window}_mean"] = rolling.mean().reset_index(level=0, drop=True).reindex(df.index)
            new_cols[f"{col}_roll{window}_std"] = rolling.std().reset_index(level=0, drop=True).reindex(df.index).fillna(0)
        for span in EMA_SPANS:
            new_cols[f"{col}_ema{span}"] = shifted_group.ewm(span=span, adjust=False).mean().reset_index(level=0, drop=True).reindex(df.index)
        for period in DIFF_PERIODS:
            new_cols[f"{col}_diff{period}"] = shifted_group.diff(period).fillna(0)
        count = shifted.notna().groupby(group, sort=False).cumsum()
        total = shifted.fillna(0).groupby(group, sort=False).cumsum()
        squares = shifted.fillna(0).pow(2).groupby(group, sort=False).cumsum()
        new_cols[f"{col}_cum_mean"] = total / count.replace(0, np.nan)
        new_cols[f"{col}_cum_std"] = np.sqrt(((squares - total.pow(2) / count.replace(0, np.nan)) / (count - 1).where(count > 1)).clip(lower=0)).fillna(0)
    features = pd.DataFrame(new_cols, index=df.index)
    keys = pd.MultiIndex.from_frame(df[["player", "match_date"]])
    first = ~keys.duplicated()
    positions = pd.Series(np.flatnonzero(first), index=keys[first]).loc[keys].to_numpy()
    features = features.iloc[positions].set_axis(df.index)
    return pd.concat([df, features], axis=1)


def add_context_features(df: pd.DataFrame) -> pd.DataFrame:
    """Use only completed earlier matches; same-day targets are excluded."""
    df = df.drop(columns=["venue_avg_pts", "opp_avg_pts", "feature_schema_version"], errors="ignore").copy()
    if "available_date" not in df:
        df["available_date"] = df["match_date"]
    df["available_date"] = pd.to_datetime(df["available_date"])
    for column, output in (("venue", "venue_avg_pts"), ("opponent", "opp_avg_pts")):
        daily = df.groupby([column, "available_date"])["total_points"].agg(["sum", "count"]).reset_index()
        daily = daily.sort_values([column, "available_date"])
        daily[output] = daily.groupby(column)["sum"].cumsum() / daily.groupby(column)["count"].cumsum()
        left = df[[column, "match_date"]].copy()
        left["_position"] = np.arange(len(df))
        merged = pd.merge_asof(left.sort_values("match_date"), daily.sort_values("available_date"),
                               left_on="match_date", right_on="available_date", by=column,
                               direction="backward", allow_exact_matches=False)
        df[output] = merged.sort_values("_position")[output].to_numpy()
        df[output] = df[output].fillna(df["total_points_cum_mean"]).fillna(0)
    df["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    return df


def process_format(fmt: str, json_path: Path):
    print(f"\n{'='*60}\nFormat: {fmt.upper()}\n{'='*60}")
    parquet_path = DATA_PROCESSED / f"features_{fmt}.parquet"
    out          = DATA_PROCESSED / f"features_{fmt}.csv"
    train_out    = DATA_PROCESSED / f"train_{fmt}.csv"
    test_out     = DATA_PROCESSED / f"test_{fmt}.csv"

    df = flatten_json(json_path, fmt)
    df = add_context_features(add_ts_features(df))
    df = df.replace([np.inf, -np.inf], 0)
    df.to_csv(out, index=False)
    df.to_parquet(parquet_path, engine="pyarrow")

    cutoff = pd.Timestamp(TRAIN_CUTOFF)
    train = df[(df["match_date"] <= cutoff) & (df["available_date"] <= cutoff)]
    test = df[(df["match_date"] > cutoff) & (df["match_date"] <= pd.Timestamp(date.today() - timedelta(days=1)))]
    train.to_csv(train_out, index=False)
    test.to_csv(test_out,  index=False)
    print(f"  [OK] Train: {len(train):,} (<= {TRAIN_CUTOFF})  |  Test: {len(test):,} (> {TRAIN_CUTOFF})")



def main():
    print("NEW_X1 — Feature Engineering (Vectorized)")
    print(f"Training cutoff: {TRAIN_CUTOFF}")

    for fmt, path in FORMATS.items():
        if not path.exists():
            print(f"\n[WARN] Skipping {fmt} — {path.name} not found")
            continue
        process_format(fmt, path)

    print("\n[OK] Feature engineering complete.")


if __name__ == "__main__":
    main()
