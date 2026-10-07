"""
NEW_X1 — Model Training
Trains format-specific models on the feature-engineered CSVs.

T20:      CatBoostRegressor   (loss=MAE, native categoricals, early stopping)
ODI/Test: TriBE Ensemble      (CatBoost + XGBoost + LightGBM → LinearRegression meta)
          Stacking uses cross_val_predict (OOF) to prevent meta-model leakage.

Saves to model_artifacts/:
  ProductUI_Model        ← CatBoost T20 (exact name required, no extension)
  tribe_odi.pkl
  tribe_test.pkl
  t20_metrics.json
  odi_metrics.json
  test_metrics.json
"""

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from data_processing.safe_publish import promote
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.base import clone
from sklearn.model_selection import TimeSeriesSplit
from datetime import date, timedelta

warnings.filterwarnings("ignore")


try:
    from catboost import CatBoostRegressor
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False
    print("⚠  CatBoost not installed — run: pip install catboost")

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("⚠  XGBoost not installed")

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    print("⚠  LightGBM not installed")

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
DATA_PROCESSED  = BASE / "data" / "processed"
MODEL_ARTIFACTS = BASE / "model_artifacts"
MODEL_ARTIFACTS.mkdir(parents=True, exist_ok=True)

TRAIN_CUTOFF = "2025-06-30"
FEATURE_SCHEMA_VERSION = 2


# ─────────────────────────────────────────────
# Columns that are NOT features (metadata + target)
# ─────────────────────────────────────────────
NON_FEATURE_COLS = {
    "player", "match_key", "match_date", "venue", "opponent",
    "format", "total_points", "feature_schema_version", "available_date",
    # raw stats used to BUILD features but not used directly as features
    "total_runs", "avg_runs_per_inning", "boundaries", "sixes", "fours",
    "wickets", "catches_taken", "stumped_outs_made", "run_outs_made",
    "balls_faced", "avg_balls_faced_per_inning", "avg_batting_sr_per_inning",
    "overs_bowled", "bowls_bowled", "avg_economy_rate_per_inning",
    "average_consecutive_dot_balls", "runs_given", "runs_given_ball_per_inning",
    "batting_sr_aa", "batting_points", "bowling_points", "fielding_points",
}

CAT_FEATURES = ["venue", "opponent"]  # CatBoost handles these natively


def load_train_test(fmt: str):
    """Load train/test CSVs for a format."""
    train_path = DATA_PROCESSED / f"train_{fmt}.csv"
    test_path  = DATA_PROCESSED / f"test_{fmt}.csv"

    if not train_path.exists():
        raise FileNotFoundError(
            f"Missing {train_path}\n"
            f"Run data_processing/feature_engineering.py first."
        )

    train = pd.read_csv(train_path, parse_dates=["match_date"])
    test  = pd.read_csv(test_path,  parse_dates=["match_date"]) if test_path.exists() else pd.DataFrame()

    for label, frame in (("train", train), ("test", test)):
        if not frame.empty and ("feature_schema_version" not in frame or not frame["feature_schema_version"].eq(FEATURE_SCHEMA_VERSION).all()):
            raise ValueError(f"{label} dataset has obsolete features; rebuild feature engineering first")
    if train["match_date"].gt(pd.Timestamp(TRAIN_CUTOFF)).any() or pd.to_datetime(train["available_date"]).gt(pd.Timestamp(TRAIN_CUTOFF)).any():
        raise ValueError("Training dataset contains matches beyond the hard cutoff")
    train = train.sort_values(["match_date", "match_key", "player"]).reset_index(drop=True)
    if not test.empty:
        test = test[(test["match_date"] > pd.Timestamp(TRAIN_CUTOFF)) & (test["match_date"] <= pd.Timestamp(date.today() - timedelta(days=1)))].sort_values(["match_date", "match_key", "player"]).reset_index(drop=True)
    print(f"  Train: {len(train):,} rows  |  Test: {len(test):,} rows")
    return train, test


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    """Return all numeric feature columns (excludes metadata + target)."""
    return [c for c in df.columns
            if c not in NON_FEATURE_COLS and not c.startswith("career_")
            and df[c].dtype in [np.float64, np.float32, np.int64, np.int32]]


def prep_xy(df: pd.DataFrame, feature_cols: list[str]):
    """Extract X (features) and y (target), drop any remaining NaNs."""
    X = df[feature_cols].copy()
    y = df["total_points"].copy()

    # Fill NaN with 0 (happens at start of player career)
    X = X.fillna(0)
    X = X.replace([np.inf, -np.inf], 0)

    mask = y.notna()
    return X[mask], y[mask]


# ─────────────────────────────────────────────────────────────────
# T20 — CatBoost single model
# ─────────────────────────────────────────────────────────────────
def train_t20(train: pd.DataFrame, test: pd.DataFrame):
    """Train CatBoostRegressor on T20 data."""
    if not HAS_CATBOOST:
        raise RuntimeError("CatBoost not available")

    print("\n--- T20 CatBoost ---")
    feature_cols = get_feature_cols(train)
    print(f"  Features: {len(feature_cols)}")

    X_train, y_train = prep_xy(train, feature_cols)

    # Identify which feature_cols are categorical
    cat_idx = [i for i, c in enumerate(feature_cols) if c in CAT_FEATURES]

    model = CatBoostRegressor(
        iterations=1000,
        learning_rate=0.05,
        depth=8,
        loss_function="MAE",
        eval_metric="MAE",
        random_seed=42,
        verbose=100,
        early_stopping_rounds=50,
    )

    # Split whole dates so no match spans training and validation.
    dates = np.sort(train.loc[X_train.index, "match_date"].unique())
    boundary = dates[max(1, int(len(dates) * 0.9))]
    earlier = train.loc[X_train.index, "match_date"] < boundary
    X_tr, y_tr = X_train.loc[earlier], y_train.loc[earlier]
    X_val, y_val = X_train.loc[~earlier], y_train.loc[~earlier]

    model.fit(
        X_tr, y_tr,
        eval_set=(X_val, y_val),
        cat_features=cat_idx if cat_idx else None,
        use_best_model=True,
    )

    best_iterations = model.tree_count_
    model = CatBoostRegressor(iterations=best_iterations, learning_rate=0.05, depth=8, loss_function="MAE", random_seed=42, verbose=False, thread_count=4)
    model.fit(X_train, y_train)

    # Evaluate on test set
    metrics = {}
    if not test.empty:
        X_test, y_test = prep_xy(test, feature_cols)
        preds = model.predict(X_test)
        preds = np.clip(preds, 0, None)  # no negative performance scores
        metrics = {
            "MAE":  round(float(mean_absolute_error(y_test, preds)), 4),
            "RMSE": round(float(np.sqrt(mean_squared_error(y_test, preds))), 4),
            "R2":   round(float(r2_score(y_test, preds)), 4),
            "n_test": len(y_test),
        }
        print(f"  Test MAE: {metrics['MAE']}  RMSE: {metrics['RMSE']}  R2: {metrics['R2']}")

    # Save — EXACT name required
    save_path = MODEL_ARTIFACTS / "ProductUI_Model"
    temporary_model = save_path.with_name(save_path.name + ".tmp")
    model.save_model(str(temporary_model))
    # Also save feature list for inference
    meta = {"feature_cols": feature_cols, "format": "t20", "cutoff": TRAIN_CUTOFF, "feature_schema_version": FEATURE_SCHEMA_VERSION}
    meta_path = MODEL_ARTIFACTS / "ProductUI_Model_meta.pkl"
    temporary_meta = meta_path.with_name(meta_path.name + ".tmp")
    joblib.dump(meta, temporary_meta)
    from model.predict_model import validate_model_metadata
    def validate_meta(candidate):
        validate_model_metadata(joblib.load(candidate))
    def validate_catboost(candidate):
        check = CatBoostRegressor()
        check.load_model(str(candidate))
    promote(temporary_meta, meta_path, validate=validate_meta)
    promote(temporary_model, save_path, validate=validate_catboost)
    print(f"  [OK] Saved: {save_path}")

    return model, feature_cols, metrics


# ─────────────────────────────────────────────────────────────────
# TriBE Ensemble (ODI + Test)
# ─────────────────────────────────────────────────────────────────
def build_tribe_base_models():
    """Instantiate the three base regressors."""
    models = {}

    if HAS_CATBOOST:
        models["catboost"] = CatBoostRegressor(
            iterations=500,
            learning_rate=0.05,
            depth=7,
            loss_function="MAE",
            random_seed=42,
            verbose=0,
            thread_count=4,
        )

    if HAS_XGB:
        models["xgboost"] = xgb.XGBRegressor(
            n_estimators=500,
            max_depth=7,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            tree_method="hist",
            n_jobs=4,
            objective="reg:absoluteerror",
        )

    if HAS_LGB:
        models["lightgbm"] = lgb.LGBMRegressor(
            n_estimators=500,
            max_depth=7,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
            n_jobs=4,
        )

    if not models:
        raise RuntimeError("No ML libraries available")

    return models


def train_tribe(train: pd.DataFrame, test: pd.DataFrame, fmt: str):
    """
    TriBE: CatBoost + XGBoost + LightGBM → LinearRegression meta-model.
    OOF stacking: cross_val_predict with 5-fold CV prevents meta-model leakage.
    """
    print(f"\n--- {fmt.upper()} TriBE Ensemble ---")
    feature_cols = get_feature_cols(train)
    print(f"  Features: {len(feature_cols)}")

    X_train, y_train = prep_xy(train, feature_cols)

    base_models = build_tribe_base_models()
    dates = train.loc[X_train.index, "match_date"]
    unique_dates = np.sort(dates.unique())
    splits = []
    for train_days, validation_days in TimeSeriesSplit(n_splits=5).split(unique_dates):
        tr = np.flatnonzero(dates.isin(unique_dates[train_days]).to_numpy())
        va = np.flatnonzero(dates.isin(unique_dates[validation_days]).to_numpy())
        assert dates.iloc[tr].max() < dates.iloc[va].min()
        splits.append((tr, va))

    oof_preds, fitted_base = {}, {}
    for name, model in base_models.items():
        print(f"  Forward OOF predict: {name}...", flush=True)
        oof = np.full(len(X_train), np.nan)
        for tr, va in splits:
            fold_model = clone(model)
            fold_model.fit(X_train.iloc[tr], y_train.iloc[tr])
            oof[va] = fold_model.predict(X_train.iloc[va])
        oof_preds[name] = oof
        model.fit(X_train, y_train)
        fitted_base[name] = model

    meta_X_train = np.column_stack(list(oof_preds.values()))
    usable = np.isfinite(meta_X_train).all(axis=1)
    meta_model = LinearRegression(positive=True)
    meta_model.fit(meta_X_train[usable], y_train.iloc[np.flatnonzero(usable)])

    print(f"  Meta weights: { {k: round(float(w), 3) for k, w in zip(oof_preds.keys(), meta_model.coef_)} }")

    # --- Evaluate on test ---
    metrics = {}
    if not test.empty:
        X_test, y_test = prep_xy(test, feature_cols)
        base_test_preds = [fitted_base[name].predict(X_test) for name in oof_preds]
        meta_X_test = np.column_stack(base_test_preds)
        final_preds = np.clip(meta_model.predict(meta_X_test), 0, None)
        metrics = {
            "MAE":  round(float(mean_absolute_error(y_test, final_preds)), 4),
            "RMSE": round(float(np.sqrt(mean_squared_error(y_test, final_preds))), 4),
            "R2":   round(float(r2_score(y_test, final_preds)), 4),
            "n_test": len(y_test),
        }
        print(f"  Test MAE: {metrics['MAE']}  RMSE: {metrics['RMSE']}  R2: {metrics['R2']}")

    # --- Save ensemble ---
    tribe_bundle = {
        "base_models":    fitted_base,
        "meta_model":     meta_model,
        "feature_cols":   feature_cols,
        "base_model_names": list(oof_preds.keys()),
        "format":         fmt,
        "cutoff":         TRAIN_CUTOFF,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
    }
    save_path = MODEL_ARTIFACTS / f"tribe_{fmt}.pkl"
    temporary_bundle = save_path.with_name(save_path.name + ".tmp")
    joblib.dump(tribe_bundle, temporary_bundle)
    from model.predict_model import validate_model_metadata
    promote(temporary_bundle, save_path,
            validate=lambda candidate: validate_model_metadata(joblib.load(candidate)))
    print(f"  [OK] Saved: {save_path}")

    return tribe_bundle, metrics


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("NEW_X1 — Model Training")
    print("Training cutoff:", TRAIN_CUTOFF)
    print("=" * 60)

    all_metrics = {}

    # ── T20 ──────────────────────────────────
    print("\n[1/3] T20 — CatBoost")
    try:
        train_t20_df, test_t20_df = load_train_test("t20")
        _, _, m = train_t20(train_t20_df, test_t20_df)
        all_metrics["t20"] = m
        (MODEL_ARTIFACTS / "t20_metrics.json").write_text(json.dumps(m, indent=2))
    except Exception as e:
        print(f"  [FAIL] T20 training failed: {e}")

    # ── ODI ──────────────────────────────────
    print("\n[2/3] ODI — TriBE")
    try:
        train_odi_df, test_odi_df = load_train_test("odi")
        _, m = train_tribe(train_odi_df, test_odi_df, "odi")
        all_metrics["odi"] = m
        (MODEL_ARTIFACTS / "odi_metrics.json").write_text(json.dumps(m, indent=2))
    except Exception as e:
        print(f"  [FAIL] ODI training failed: {e}")

    # ── Test ─────────────────────────────────
    print("\n[3/3] Test — TriBE")
    try:
        train_test_df, test_test_df = load_train_test("test")
        _, m = train_tribe(train_test_df, test_test_df, "test")
        all_metrics["test"] = m
        (MODEL_ARTIFACTS / "test_metrics.json").write_text(json.dumps(m, indent=2))
    except Exception as e:
        print(f"  [FAIL] Test training failed: {e}")

    # ── Summary ──────────────────────────────
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    for fmt, m in all_metrics.items():
        if m:
            print(f"  {fmt.upper():<6} MAE={m.get('MAE','N/A')}  RMSE={m.get('RMSE','N/A')}  R2={m.get('R2','N/A')}")

    print(f"\nAll models saved to: {MODEL_ARTIFACTS}")
    if len(all_metrics) != 3:
        raise SystemExit("Training failed for one or more formats")
    print("[OK] Training complete.")



if __name__ == "__main__":
    main()
