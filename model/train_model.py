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
from sklearn.model_selection import cross_val_predict, KFold

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


# ─────────────────────────────────────────────
# Columns that are NOT features (metadata + target)
# ─────────────────────────────────────────────
NON_FEATURE_COLS = {
    "player", "match_key", "match_date", "venue", "opponent",
    "format", "total_points",
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

    print(f"  Train: {len(train):,} rows  |  Test: {len(test):,} rows")
    return train, test


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    """Return all numeric feature columns (excludes metadata + target)."""
    return [c for c in df.columns
            if c not in NON_FEATURE_COLS
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

    # Use 10% of train as validation for early stopping
    val_size = max(1, int(0.1 * len(X_train)))
    X_val, y_val = X_train.iloc[-val_size:], y_train.iloc[-val_size:]
    X_tr,  y_tr  = X_train.iloc[:-val_size], y_train.iloc[:-val_size]

    model.fit(
        X_tr, y_tr,
        eval_set=(X_val, y_val),
        cat_features=cat_idx if cat_idx else None,
        use_best_model=True,
    )

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
    model.save_model(str(save_path))
    print(f"  [OK] Saved: {save_path}")


    # Also save feature list for inference
    meta = {"feature_cols": feature_cols, "format": "t20", "cutoff": TRAIN_CUTOFF}
    joblib.dump(meta, MODEL_ARTIFACTS / "ProductUI_Model_meta.pkl")

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
    kf = KFold(n_splits=5, shuffle=False)  # no shuffle — preserve time order

    # --- Stage 1: OOF predictions from base models ---
    oof_preds = {}
    fitted_base = {}

    for name, model in base_models.items():
        print(f"  OOF predict: {name}...")
        # For CatBoost, drop cat columns to avoid issues in cross_val_predict
        X_fit = X_train.copy()

        oof = cross_val_predict(
            model, X_fit, y_train,
            cv=kf, method="predict", n_jobs=-1
        )
        oof_preds[name] = oof

        # Refit on full training data
        model.fit(X_fit, y_train)
        fitted_base[name] = model

    # --- Stage 2: Meta-model on OOF predictions ---
    meta_X_train = np.column_stack(list(oof_preds.values()))
    meta_model = LinearRegression(positive=True)  # weights must be ≥ 0
    meta_model.fit(meta_X_train, y_train)

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
    }
    save_path = MODEL_ARTIFACTS / f"tribe_{fmt}.pkl"
    joblib.dump(tribe_bundle, save_path)
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
    print("[OK] Training complete.")



if __name__ == "__main__":
    main()
