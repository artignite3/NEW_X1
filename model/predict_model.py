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
import hashlib
import json
import re
import warnings
from datetime import datetime, date, timedelta
from model.data_contract import FEATURE_SCHEMA_VERSION, TRAIN_CUTOFF
from data_processing.safe_publish import last_good
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
_MODEL_SOURCES: dict = {}
_DF_SOURCES: dict = {}


def get_model(fmt: str):
    """Cached load with a compatible last-good artifact if publication fails."""
    fmt = fmt.lower()
    primary = ([MODEL_ARTIFACTS / "ProductUI_Model", MODEL_ARTIFACTS / "ProductUI_Model_meta.pkl"]
               if fmt == "t20" else [MODEL_ARTIFACTS / f"tribe_{fmt}.pkl"])
    candidates = primary + [last_good(p) for p in primary]
    stamp = tuple(_model_stamp(p) for p in candidates)
    if fmt not in _MODEL_CACHE or _MODEL_STAMPS.get(fmt) != stamp:
        _MODEL_CACHE[fmt] = load_model(fmt)
        _MODEL_STAMPS[fmt] = stamp
    return _MODEL_CACHE[fmt]


def _model_stamp(path):
    if not path.exists():
        return None
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return digest


def load_model(fmt: str):
    """Only a complete, schema-compatible model pair can be used."""
    errors = []
    if fmt == "t20":
        primary_model = MODEL_ARTIFACTS / "ProductUI_Model"
        primary_meta = MODEL_ARTIFACTS / "ProductUI_Model_meta.pkl"
        for model_path, meta_path, source in ((primary_model, primary_meta, "current"),
                                              (last_good(primary_model), last_good(primary_meta), "last_good")):
            try:
                meta = joblib.load(meta_path)
                validate_model_metadata(meta)
                from catboost import CatBoostRegressor
                model = CatBoostRegressor()
                model.load_model(str(model_path))
                if list(model.feature_names_) != list(meta["feature_cols"]):
                    raise ValueError("T20 model and metadata feature lists differ")
                _MODEL_SOURCES[fmt] = source
                return "catboost", model, meta["feature_cols"]
            except Exception as error:
                errors.append(f"{source}: {type(error).__name__}")
    else:
        primary = MODEL_ARTIFACTS / f"tribe_{fmt}.pkl"
        for path, source in ((primary, "current"), (last_good(primary), "last_good")):
            try:
                bundle = joblib.load(path)
                validate_model_metadata(bundle)
                validate_tribe_bundle(bundle)
                _MODEL_SOURCES[fmt] = source
                return "tribe", bundle, bundle["feature_cols"]
            except Exception as error:
                errors.append(f"{source}: {type(error).__name__}")
    raise FileNotFoundError(f"No compatible {fmt} model available ({'; '.join(errors)})")


def validate_model_metadata(meta):
    if not isinstance(meta, dict):
        raise FileNotFoundError("Model metadata must be an object")
    cols = meta.get("feature_cols")
    if (not isinstance(cols, list) or not cols
        or not all(isinstance(c, str) and c.strip() for c in cols)
        or len(set(cols)) != len(cols)):
        raise FileNotFoundError("Model feature list must contain unique, nonempty names")
    if (meta.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
        or meta.get("cutoff") != TRAIN_CUTOFF
        or any(c.startswith("career_") for c in cols)):
        raise FileNotFoundError("Model uses obsolete/leaking features. Rebuild datasets and retrain all models.")


def validate_tribe_bundle(bundle):
    """Check the executable ensemble before selecting it over a healthy backup."""
    names = bundle.get("base_model_names")
    models = bundle.get("base_models")
    cols = bundle["feature_cols"]
    if (not isinstance(names, list) or len(names) != 3
        or set(names) != {"catboost", "xgboost", "lightgbm"}
        or not isinstance(models, dict)):
        raise ValueError("TriBE requires three named base learners")
    sample = pd.DataFrame(np.zeros((1, len(cols))), columns=cols)
    predictions = []
    for name in names:
        learner = models.get(name)
        if not callable(getattr(learner, "predict", None)):
            raise ValueError(f"Missing predictor: {name}")
        feature_names = getattr(learner, "feature_names_in_", None)
        if feature_names is None:
            feature_names = getattr(learner, "feature_names_", None)
        if feature_names is not None and list(feature_names) != cols:
            raise ValueError(f"Feature order mismatch: {name}")
        count = getattr(learner, "n_features_in_", len(cols))
        # Loaded CatBoost artifacts can report zero here; their stored names
        # and the real prediction below still verify the input contract.
        if count != len(cols) and not (count == 0 and feature_names is not None):
            raise ValueError(f"Feature count mismatch: {name}")
        values = np.asarray(learner.predict(sample), dtype=float)
        if values.shape != (1,) or not np.isfinite(values).all():
            raise ValueError(f"Invalid prediction: {name}")
        predictions.append(values)
    meta = bundle.get("meta_model")
    if not callable(getattr(meta, "predict", None)):
        raise ValueError("Missing fitted meta-model")
    if getattr(meta, "n_features_in_", len(names)) != len(names):
        raise ValueError("Meta-model feature count mismatch")
    values = np.asarray(meta.predict(np.column_stack(predictions)), dtype=float)
    if values.shape != (1,) or not np.isfinite(values).all():
        raise ValueError("Invalid meta-model prediction")


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
    """Load a versioned dataset, recovering from a validated previous copy."""
    fmt = fmt.lower()
    parquet = DATA_PROCESSED / f"features_{fmt}.parquet"
    csv = DATA_PROCESSED / f"features_{fmt}.csv"
    candidates = (parquet, last_good(parquet), csv, last_good(csv))
    stamp = tuple((p.stat().st_mtime_ns, p.stat().st_ctime_ns, p.stat().st_size)
                  if p.exists() else None for p in candidates)
    if fmt in _DF_CACHE and _DF_STAMPS.get(fmt) == stamp:
        return _DF_CACHE[fmt]
    errors = []
    for path in candidates:
        try:
            if path.suffix == ".parquet" or path.name.endswith(".parquet.last_good"):
                df = pd.read_parquet(path)
            else:
                df = pd.read_csv(path, parse_dates=["match_date", "available_date"])
            if "feature_schema_version" not in df or not df.feature_schema_version.eq(FEATURE_SCHEMA_VERSION).all():
                raise ValueError("obsolete feature schema")
            if not pd.api.types.is_datetime64_any_dtype(df["match_date"]):
                df["match_date"] = pd.to_datetime(df["match_date"])
            df["available_date"] = pd.to_datetime(df["available_date"])
            _DF_SOURCES[fmt] = "last_good" if path.name.endswith(".last_good") else "current"
            for other in list(_DF_CACHE):
                if other != fmt:
                    _DF_CACHE.pop(other, None)
                    _DF_STAMPS.pop(other, None)
            _DF_STAMPS[fmt] = stamp
            _DF_CACHE[fmt] = df
            return df
        except Exception as error:
            errors.append(f"{path.name}: {type(error).__name__}")
    raise FileNotFoundError(f"No compatible {fmt} features ({'; '.join(errors)})")


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
