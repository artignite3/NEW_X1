"""
NEW_X1 — Prediction & Evaluation
Loads trained models and generates:
  1. Per-player performance score predictions for a given squad + date
  2. MAE evaluation CSV (Model UI use-case)

Usage:
  # Single match prediction
  python predict_model.py --team1 India --team2 Australia --date 2024-08-15 --format t20

  # Date-range evaluation (Model UI)
  python predict_model.py --mode eval --train-end 2024-06-30 --test-start 2024-07-01 --test-end 2024-12-31
"""

import argparse
import json
import re
import warnings
from datetime import datetime, date, timedelta
from model.data_contract import FEATURE_SCHEMA_VERSION, TRAIN_CUTOFF
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
DATA_PROCESSED  = BASE / "data" / "processed"
MODEL_ARTIFACTS = BASE / "model_artifacts"
OUTPUTS         = BASE / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

NON_FEATURE_COLS = {
    "player", "match_key", "match_date", "venue", "opponent",
    "format", "total_points",
    "total_runs", "avg_runs_per_inning", "boundaries", "sixes", "fours",
    "wickets", "catches_taken", "stumped_outs_made", "run_outs_made",
    "balls_faced", "avg_balls_faced_per_inning", "avg_batting_sr_per_inning",
    "overs_bowled", "bowls_bowled", "avg_economy_rate_per_inning",
    "average_consecutive_dot_balls", "runs_given", "runs_given_ball_per_inning",
    "batting_sr_aa", "batting_points", "bowling_points", "fielding_points",
}


# ─────────────────────────────────────────────
# Model Loading (cached for API request speed)
# ─────────────────────────────────────────────
_MODEL_CACHE: dict = {}
_DF_CACHE: dict = {}
_MODEL_STAMPS: dict = {}
_DF_STAMPS: dict = {}


def get_model(fmt: str):
    """Cached load_model — avoids re-deserializing heavy model bundles per request."""
    fmt = fmt.lower()
    paths = ([MODEL_ARTIFACTS / "ProductUI_Model", MODEL_ARTIFACTS / "ProductUI_Model_meta.pkl"]
             if fmt == "t20" else [MODEL_ARTIFACTS / f"tribe_{fmt}.pkl"])
    stamp = tuple(p.stat().st_mtime_ns if p.exists() else None for p in paths)
    if fmt not in _MODEL_CACHE or _MODEL_STAMPS.get(fmt) != stamp:
        _MODEL_CACHE[fmt] = load_model(fmt)
        _MODEL_STAMPS[fmt] = stamp
    return _MODEL_CACHE[fmt]


def load_model(fmt: str):
    """Load the correct model for a format. Returns (model_type, model_object)."""
    if fmt == "t20":
        model_path = MODEL_ARTIFACTS / "ProductUI_Model"
        meta_path  = MODEL_ARTIFACTS / "ProductUI_Model_meta.pkl"
        if not model_path.exists():
            raise FileNotFoundError(
                f"ProductUI_Model not found in {MODEL_ARTIFACTS}\n"
                f"Run model/train_model.py first."
            )
        from catboost import CatBoostRegressor
        model = CatBoostRegressor()
        model.load_model(str(model_path))
        meta = joblib.load(meta_path) if meta_path.exists() else {}
        validate_model_metadata(meta)
        return "catboost", model, meta["feature_cols"]
    else:
        bundle_path = MODEL_ARTIFACTS / f"tribe_{fmt}.pkl"
        if not bundle_path.exists():
            raise FileNotFoundError(
                f"tribe_{fmt}.pkl not found in {MODEL_ARTIFACTS}\n"
                f"Run model/train_model.py first."
            )
        bundle = joblib.load(bundle_path)
        validate_model_metadata(bundle)
        return "tribe", bundle, bundle["feature_cols"]


def validate_model_metadata(meta):
    if (meta.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
        or meta.get("cutoff") != TRAIN_CUTOFF
        or any(c.startswith("career_") for c in meta.get("feature_cols", []))):
        raise FileNotFoundError("Model uses obsolete/leaking features. Rebuild datasets and retrain all models.")


def tribe_predict(bundle: dict, X: pd.DataFrame) -> np.ndarray:
    """Run TriBE ensemble inference."""
    base_preds = [
        bundle["base_models"][name].predict(X)
        for name in bundle["base_model_names"]
    ]
    meta_X = np.column_stack(base_preds)
    preds = bundle["meta_model"].predict(meta_X)
    return np.clip(preds, 0, None)


# ─────────────────────────────────────────────
# Feature preparation for new / upcoming players
# ─────────────────────────────────────────────
def get_player_features(
    player_name: str,
    fmt: str,
    cutoff_date: str,
    feature_cols: list[str],
) -> pd.DataFrame | None:
    """
    Load a player's pre-computed feature row as of cutoff_date.
    Returns a 1-row DataFrame ready for prediction.
    """
    rows = build_request_features([player_name], fmt, cutoff_date, feature_cols)
    return rows.get(player_name)


def _load_features_dataset(fmt: str) -> pd.DataFrame:
    """Cached feature dataset loader (parquet preferred, csv fallback)."""
    fmt = fmt.lower()
    parquet_path = DATA_PROCESSED / f"features_{fmt}.parquet"
    csv_path     = DATA_PROCESSED / f"features_{fmt}.csv"

    selected_path = parquet_path if parquet_path.exists() else csv_path
    stamp = selected_path.stat().st_mtime_ns if selected_path.exists() else None
    if fmt in _DF_CACHE and _DF_STAMPS.get(fmt) == stamp:
        return _DF_CACHE[fmt]
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        if not pd.api.types.is_datetime64_any_dtype(df["match_date"]):
            df["match_date"] = pd.to_datetime(df["match_date"])
    elif csv_path.exists():
        df = pd.read_csv(csv_path, parse_dates=["match_date"])
    else:
        raise FileNotFoundError(f"Feature dataset not found for format {fmt}")

    if "feature_schema_version" not in df or not df.feature_schema_version.eq(FEATURE_SCHEMA_VERSION).all():
        raise FileNotFoundError("Obsolete feature dataset; rebuild feature engineering first")
    df["available_date"] = pd.to_datetime(df["available_date"])
    _DF_STAMPS[fmt] = stamp
    _DF_CACHE[fmt] = df
    return df


def build_request_features(players, fmt, match_date, feature_cols, venue=None, opponents=None):
    """Construct new pre-match rows, including the most recently completed game."""
    from data_processing.feature_engineering import RAW_STATS, add_ts_features
    dataset = _load_features_dataset(fmt)
    cutoff = pd.Timestamp(match_date)
    completed = dataset[(dataset.match_date < cutoff) & (dataset.available_date < cutoff)]
    history = completed[completed.player.isin(players)]
    columns = ["player", "match_key", "match_date", "available_date", "venue", "opponent", "total_points"] + RAW_STATS
    rows = []
    known = set(history.player)
    for player in players:
        if player not in known:
            continue
        latest = history[history.player.eq(player)].sort_values("match_date").iloc[-1]
        rows.append({"player": player, "match_key": "__prediction__", "match_date": cutoff,
                     "available_date": cutoff, "venue": venue or latest.venue,
                     "opponent": (opponents or {}).get(player, latest.opponent),
                     **{c: 0.0 for c in RAW_STATS + ["total_points"]}})
    if not rows:
        return {}
    combined = pd.concat([history[columns], pd.DataFrame(rows)], ignore_index=True).sort_values(["player", "match_date", "match_key"]).reset_index(drop=True)
    engineered = add_ts_features(combined)
    result = {}
    for player in known:
        row = engineered[(engineered.player == player) & (engineered.match_key == "__prediction__")].copy()
        if row.empty:
            continue
        for key, output in (("venue", "venue_avg_pts"), ("opponent", "opp_avg_pts")):
            values = completed.loc[completed[key].eq(row.iloc[0][key]), "total_points"]
            row[output] = float(values.mean()) if len(values) else float(row.iloc[0].total_points_cum_mean)
        result[player] = row.reindex(columns=feature_cols, fill_value=0).fillna(0).replace([np.inf, -np.inf], 0)
    return result


def predict_squad(
    players: list[str],
    fmt: str,
    match_date: str,
    return_details: bool = False,
    venue: str | None = None,
    opponents: dict | None = None,
):
    """
    Predict performance scores for a list of players.
    Loads dataset/model once per process (cached) for fast repeat requests.

    When return_details=True, returns (predictions_df, details) where details
    carries the per-player latest feature row plus the model handle — used by
    the SHAP explainability layer.
    """
    model_type, model, feature_cols = get_model(fmt)
    rows = []
    features_by_player = build_request_features(players, fmt, match_date, feature_cols, venue, opponents)
    for player in players:
        feat_row = features_by_player.get(player)
        if feat_row is None:
            rows.append({"player": player, "predicted_score": 25.0, "has_history": False})
            continue

        if model_type == "catboost":
            pred = float(np.clip(model.predict(feat_row)[0], 0, None))
        else:
            pred = float(tribe_predict(model, feat_row)[0])

        rows.append({"player": player, "predicted_score": round(pred, 2), "has_history": True})
        if return_details:
            features_by_player[player] = feat_row

    out = pd.DataFrame(rows).sort_values("predicted_score", ascending=False).reset_index(drop=True)
    if return_details:
        return out, {
            "model_type": model_type,
            "model": model,
            "feature_cols": feature_cols,
            "features": features_by_player,
        }
    return out



# ─────────────────────────────────────────────
# Evaluation — MAE over test period
# ─────────────────────────────────────────────
def evaluate_on_test(
    fmt: str,
    test_start: str,
    test_end: str,
    output_csv: str | None = None,
) -> pd.DataFrame:
    """
    For every match in [test_start, test_end]:
      - Predict performance scores for all players
      - Compute actual dream-team total (top 11 by actual score)
      - Compute predicted dream-team total (top 11 by predicted score)
      - MAE = |actual_total - predicted_total|

    Returns match-level results DataFrame.
    Saves CSV to outputs/ if output_csv is given.
    """
    parquet_path = DATA_PROCESSED / f"features_{fmt}.parquet"
    csv_path     = DATA_PROCESSED / f"features_{fmt}.csv"

    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        if not pd.api.types.is_datetime64_any_dtype(df["match_date"]):
            df["match_date"] = pd.to_datetime(df["match_date"])
    elif csv_path.exists():
        df = pd.read_csv(csv_path, parse_dates=["match_date"])
    else:
        raise FileNotFoundError(f"Run feature_engineering.py first — missing {csv_path}")

    model_type, model, feature_cols = load_model(fmt)

    start = pd.Timestamp(test_start)
    end = pd.Timestamp(test_end)
    if start <= pd.Timestamp(TRAIN_CUTOFF) or end >= pd.Timestamp(date.today()) or start > end:
        raise ValueError("Evaluation must run after 2025-06-30 and end no later than yesterday")
    test_df = df[(df["match_date"] >= start) & (df["match_date"] <= end)].copy()

    if test_df.empty:
        print(f"  No test data between {test_start} and {test_end}")
        return pd.DataFrame()


    results = []

    # Group by match_key (each match = a group of player rows)
    for match_key, group in test_df.groupby("match_key"):
        group = group.copy()
        X = group[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)

        if model_type == "catboost":
            preds = np.clip(model.predict(X), 0, None)
        else:
            preds = tribe_predict(model, X)

        group["predicted_score"] = preds
        group["actual_score"]    = group["total_points"].values

        # Dream team = top 11 by actual score (ground truth)
        actual_top11  = group.nlargest(11, "actual_score")["actual_score"].sum()
        # Our predicted top 11
        pred_top11_players = group.nlargest(11, "predicted_score")
        pred_team_actual   = pred_top11_players["actual_score"].sum()

        mae_match = abs(actual_top11 - pred_team_actual)

        match_date = group["match_date"].iloc[0]
        results.append({
            "match_key":          match_key,
            "match_date":         match_date.strftime("%Y-%m-%d"),
            "format":             fmt,
            "n_players":          len(group),
            "dream_team_score":   round(actual_top11, 2),
            "predicted_team_score": round(pred_team_actual, 2),
            "MAE":                round(mae_match, 2),
        })

    results_df = pd.DataFrame(results).sort_values("match_date").reset_index(drop=True)

    overall_mae = results_df["MAE"].mean()
    print(f"  {fmt.upper()} Overall MAE: {overall_mae:.2f}  (across {len(results_df)} matches)")

    if output_csv:
        out_path = OUTPUTS / output_csv
        results_df.to_csv(out_path, index=False)
        print(f"  [OK] Results saved: {out_path}")


    return results_df


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="NEW_X1 Predict & Evaluate")
    parser.add_argument("--mode", choices=["predict", "eval"], default="predict")
    parser.add_argument("--format", default="t20", choices=["t20", "odi", "test"])

    # Predict mode args
    parser.add_argument("--players", nargs="+", help="Player names to predict for")
    parser.add_argument("--date",   help="Match date YYYY-MM-DD (predict mode)")

    # Eval mode args
    parser.add_argument("--test-start", help="Test start date YYYY-MM-DD")
    parser.add_argument("--test-end",   help="Test end date YYYY-MM-DD")
    parser.add_argument("--output-csv", default=None, help="Output CSV filename")

    args = parser.parse_args()
    fmt = args.format.lower()

    if args.mode == "predict":
        if not args.players or not args.date:
            parser.error("--players and --date required for predict mode")
        preds = predict_squad(args.players, fmt, args.date)
        print("\nPredicted Performance Scores:")
        print(preds.to_string(index=False))

    elif args.mode == "eval":
        if not args.test_start or not args.test_end:
            parser.error("--test-start and --test-end required for eval mode")

        ts = args.test_start
        te = args.test_end
        csv_name = args.output_csv or f"eval_{fmt}_{ts}_to_{te}.csv"
        evaluate_on_test(fmt, ts, te, output_csv=csv_name)


if __name__ == "__main__":
    main()
