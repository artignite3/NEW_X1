"""
NEW_X1 — M2: Chronological model evaluation
Measures (per format, on the post-cutoff window, whole matches kept together):

  - Player MAE / RMSE            — model vs a recent-form baseline
  - Selection regret             — actual points lost by picking the predicted
                                   top-11 instead of the true dream team
  - Interval coverage            — share of actuals inside pred ± 1.28 * sigma
                                   (target ~80% for the 80% interval)
  - Experience bands             — MAE by player history depth (leak-safe:
                                   cumulative count uses only past matches)

Baseline: mean of the last 3 completed matches (total_points_lag1..lag3) —
the "ensemble must earn its place" comparison. No future information touches
either side: every feature used is a shifted/rolling column.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model.predict_model import get_model, tribe_predict  # noqa: E402

TRAIN_CUTOFF = "2025-07-01"
CI_Z = 1.28
BASELINE_LAGS = ["total_points_lag1", "total_points_lag2", "total_points_lag3"]


def evaluate_format(fmt: str, max_matches: int | None = None) -> dict:
    from model.predict_model import _load_features_dataset

    df = _load_features_dataset(fmt)
    df = df[(df.match_date >= pd.Timestamp(TRAIN_CUTOFF)) & df.total_points_lag1.notna()]
    if max_matches:
        keep = df.match_key.drop_duplicates().sort_values().iloc[:max_matches]
        df = df[df.match_key.isin(keep)]
    if df.empty:
        return {"format": fmt, "status": "no eval data"}

    model_type, model, feature_cols = get_model(fmt)
    X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    df = df.copy()
    df["pred_model"] = np.clip(model.predict(X) if model_type == "catboost"
                               else tribe_predict(model, X), 0, None)
    df["pred_baseline"] = df[BASELINE_LAGS].fillna(df[BASELINE_LAGS].min()).mean(axis=1)

    sigma = df["total_points_roll7_std"].fillna(df.groupby("player")["total_points"].transform("std")).fillna(25.0)
    df["sigma"] = sigma
    df["in_ci"] = (df.total_points >= df.pred_model - CI_Z * df.sigma) & \
                  (df.total_points <= df.pred_model + CI_Z * df.sigma)

    # Experience: number of PRIOR completed matches for this player (shifted)
    df = df.sort_values(["player", "match_date"])
    df["prior_matches"] = df.groupby("player").cumcount()
    df["exp_band"] = pd.cut(df["prior_matches"], [-1, 10, 30, 10**9],
                            labels=["0-10", "11-30", "31+"])

    def mae(col):
        return float((df[col] - df.total_points).abs().mean())

    def rmse(col):
        return float(np.sqrt(((df[col] - df.total_points) ** 2).mean()))

    match_level = df.groupby("match_key").apply(
        lambda g: pd.Series({
            "actual_dream_team": g.total_points.nlargest(11).sum(),
            "predicted_team_actual": g.nlargest(11, "pred_model").total_points.sum(),
            "baseline_team_actual": g.nlargest(11, "pred_baseline").total_points.sum(),
        }), include_groups=False,
    )
    regret_model = float((match_level.actual_dream_team - match_level.predicted_team_actual).mean())
    regret_baseline = float((match_level.actual_dream_team - match_level.baseline_team_actual).mean())

    summary = {
        "format": fmt,
        "model": model_type,
        "matches": int(match_level.shape[0]),
        "player_rows": int(len(df)),
        "model_MAE": round(mae("pred_model"), 2),
        "baseline_MAE": round(mae("pred_baseline"), 2),
        "model_RMSE": round(rmse("pred_model"), 2),
        "baseline_RMSE": round(rmse("pred_baseline"), 2),
        "selection_regret_model": round(regret_model, 2),
        "selection_regret_baseline": round(regret_baseline, 2),
        "interval_coverage_pct": round(100 * float(df.in_ci.mean()), 1),
        "coverage_target_pct": 80.0,
        "mae_by_experience": {
            str(band): round(float((g.pred_model - g.total_points).abs().mean()), 2)
            for band, g in df.groupby("exp_band", observed=True)
        },
    }

    match_level.assign(format=fmt).reset_index().to_csv(
        ROOT / "outputs" / f"eval_matches_{fmt}.csv", index=False)
    return summary


def main():
    formats = sys.argv[1:] or ["t20", "odi"]
    results = []
    for fmt in formats:
        try:
            s = evaluate_format(fmt)
        except FileNotFoundError as e:
            s = {"format": fmt, "status": f"model unavailable: {e}"}
        results.append(s)
        print(json.dumps(s, indent=2), flush=True)
    (ROOT / "outputs" / "eval_summary.json").write_text(json.dumps(results, indent=2))
    print(f"[OK] outputs/eval_summary.json")


if __name__ == "__main__":
    main()
