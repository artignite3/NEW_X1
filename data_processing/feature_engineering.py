"""
NEW_X1 — Feature Engineering (Vectorized — fast)
Transforms player_fantasy_points_*.json into ML-ready feature CSVs.

Uses pandas groupby + transform instead of per-player loops.
Output files in data/processed/:
  features_{fmt}.csv   — full feature matrix (all matches)
  train_{fmt}.csv      — matches <= 2024-06-30
  test_{fmt}.csv       — matches >  2024-06-30
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
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
                "venue":      s.get("venue", "Unknown") or "Unknown",
                "opponent":   s.get("opponent", "Unknown") or "Unknown",
                "format":     fmt,
                "total_points": safe(s.get("total_points", 0)),
            }
            for col in RAW_STATS:
                row[col] = safe(s.get(col, 0))
            for col in CAREER_STATS:
                key = f"career_{col.replace(' ','_').replace('/','_').replace('%','pct')}"
                row[key] = safe(s.get(col, 0))
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
    grp = df.groupby("player", sort=False)

    new_cols = {}

    for col in tqdm(feature_cols, desc="  TS features", ncols=80):
        base = grp[col]
        shifted = base.transform(lambda s: s.shift(1))

        for lag in LAG_WINDOWS:
            new_cols[f"{col}_lag{lag}"] = grp[col].transform(lambda s: s.shift(lag))

        for w in ROLL_WINDOWS:
            roll = grp[col].transform(lambda s: s.shift(1).rolling(w, min_periods=1).mean())
            new_cols[f"{col}_roll{w}_mean"] = roll
            std = grp[col].transform(lambda s: s.shift(1).rolling(w, min_periods=1).std().fillna(0))
            new_cols[f"{col}_roll{w}_std"] = std

        for span in EMA_SPANS:
            new_cols[f"{col}_ema{span}"] = grp[col].transform(
                lambda s: s.shift(1).ewm(span=span, adjust=False).mean()
            )

        for period in DIFF_PERIODS:
            new_cols[f"{col}_diff{period}"] = shifted.groupby(
                df["player"]
            ).transform(lambda s: s.diff(period).fillna(0))

        new_cols[f"{col}_cum_mean"] = grp[col].transform(lambda s: s.shift(1).expanding().mean())
        new_cols[f"{col}_cum_std"]  = grp[col].transform(lambda s: s.shift(1).expanding().std().fillna(0))

    feat_df = pd.DataFrame(new_cols, index=df.index)
    return pd.concat([df, feat_df], axis=1)

def add_context_features(df: pd.DataFrame) -> pd.DataFrame:
    """Historical venue and opponent averages (no leakage — expanding shifted)."""
    df["venue_avg_pts"] = (
        df.groupby("venue")["total_points"]
          .transform(lambda s: s.shift(1).expanding().mean())
    )
    df["opp_avg_pts"] = (
        df.groupby("opponent")["total_points"]
          .transform(lambda s: s.shift(1).expanding().mean())
    )
    global_mean = df.groupby("player")["total_points"].transform(
        lambda s: s.shift(1).expanding().mean()
    )
    df["venue_avg_pts"] = df["venue_avg_pts"].fillna(global_mean).fillna(0)
    df["opp_avg_pts"]   = df["opp_avg_pts"].fillna(global_mean).fillna(0)
    return df

def process_format(fmt: str, json_path: Path):
    print(f"\n{'='*60}\nFormat: {fmt.upper()}\n{'='*60}")
    parquet_path = DATA_PROCESSED / f"features_{fmt}.parquet"
    out          = DATA_PROCESSED / f"features_{fmt}.csv"
    train_out    = DATA_PROCESSED / f"train_{fmt}.csv"
    test_out     = DATA_PROCESSED / f"test_{fmt}.csv"

    if parquet_path.exists():
        print(f"  features_{fmt}.parquet exists. Loading for train/test split at {TRAIN_CUTOFF}...")
        df = pd.read_parquet(parquet_path)
        if not pd.api.types.is_datetime64_any_dtype(df["match_date"]):
            df["match_date"] = pd.to_datetime(df["match_date"])
    elif out.exists():
        print(f"  features_{fmt}.csv exists. Loading for train/test split at {TRAIN_CUTOFF}...")
        df = pd.read_csv(out, parse_dates=["match_date"])
    else:
        df = flatten_json(json_path, fmt)
        df = add_ts_features(df)
        df = add_context_features(df)

        df = df.dropna(subset=["total_points_lag1"])
        df = df.replace([np.inf, -np.inf], 0)

        print(f"  Final shape: {df.shape}")
        df.to_csv(out, index=False)
        print(f"  [OK] Saved: {out.name}")
        df.to_parquet(parquet_path, engine="pyarrow")
        print(f"  [OK] Saved: {parquet_path.name}")

    cutoff = pd.Timestamp(TRAIN_CUTOFF)
    train = df[df["match_date"] <= cutoff]
    test  = df[df["match_date"] >  cutoff]
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
