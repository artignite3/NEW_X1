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
from datetime import datetime
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


def get_model(fmt: str):
    """Cached load_model — avoids re-deserializing heavy model bundles per request."""
    fmt = fmt.lower()
    if fmt not in _MODEL_CACHE:
        _MODEL_CACHE[fmt] = load_model(fmt)
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
        return "catboost", model, meta.get("feature_cols", [])
    else:
        bundle_path = MODEL_ARTIFACTS / f"tribe_{fmt}.pkl"
        if not bundle_path.exists():
            raise FileNotFoundError(
                f"tribe_{fmt}.pkl not found in {MODEL_ARTIFACTS}\n"
                f"Run model/train_model.py first."
            )
        bundle = joblib.load(bundle_path)
        return "tribe", bundle, bundle["feature_cols"]


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
    feat_path = DATA_PROCESSED / f"features_{fmt}.csv"
    if not feat_path.exists():
        return None

    # Read only matching rows to save memory
    df = pd.read_csv(feat_path, parse_dates=["match_date"])
    cutoff = pd.Timestamp(cutoff_date)

    player_df = df[
        (df["player"] == player_name) &
        (df["match_date"] <= cutoff)
    ].sort_values("match_date")

    if player_df.empty:
        return None

    # Use the most recent row (features already shifted, so this is correct)
    row = player_df.iloc[[-1]].copy()

    # Align to expected feature columns
    missing = set(feature_cols) - set(row.columns)
    for col in missing:
        row[col] = 0.0
    row = row[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    return row


def _load_features_dataset(fmt: str) -> pd.DataFrame:
    """Cached feature dataset loader (parquet preferred, csv fallback)."""
    fmt = fmt.lower()
    if fmt in _DF_CACHE:
        return _DF_CACHE[fmt]

    parquet_path = DATA_PROCESSED / f"features_{fmt}.parquet"
    csv_path     = DATA_PROCESSED / f"features_{fmt}.csv"

    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        if not pd.api.types.is_datetime64_any_dtype(df["match_date"]):
            df["match_date"] = pd.to_datetime(df["match_date"])
    elif csv_path.exists():
        df = pd.read_csv(csv_path, parse_dates=["match_date"])
    else:
        raise FileNotFoundError(f"Feature dataset not found for format {fmt}")

    _DF_CACHE[fmt] = df
    return df


def predict_squad(
    players: list[str],
    fmt: str,
    match_date: str,
    return_details: bool = False,
):
    """
    Predict performance scores for a list of players.
    Loads dataset/model once per process (cached) for fast repeat requests.

    When return_details=True, returns (predictions_df, details) where details
    carries the per-player latest feature row plus the model handle — used by
    the SHAP explainability layer.
    """
    model_type, model, feature_cols = get_model(fmt)
    df = _load_features_dataset(fmt)

    cutoff = pd.Timestamp(match_date)

    rows = []
    features_by_player: dict[str, pd.DataFrame] = {}

    for player in players:
        player_df = df[
            (df["player"] == player) &
            (df["match_date"] <= cutoff)
        ].sort_values("match_date")

        if player_df.empty:
            rows.append({"player": player, "predicted_score": 25.0, "has_history": False})
            continue

        row = player_df.iloc[[-1]].copy()
        missing = set(feature_cols) - set(row.columns)
        for col in missing:
            row[col] = 0.0
        feat_row = row[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)

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
    end   = pd.Timestamp(test_end)
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
