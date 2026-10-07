"""
NEW_X1 — Intelligence Layer: SHAP Driver Extraction
Computes per-player top feature contributions for a prediction, so the
analyst report can cite *why* a score was predicted.

Supported model kinds:
  - catboost : native SHAP via get_feature_importance(type="ShapValues")
  - xgboost / lightgbm : shap.TreeExplainer

Returns [] on any failure — the explanation layer degrades gracefully to
generic form-based reasoning.
"""

from typing import List

import numpy as np


def top_shap_features(model, feat_row, feature_cols: List[str], kind: str = "catboost",
                      top_k: int = 3) -> List[dict]:
    """
    Returns [{"feature": <raw feature name>, "impact": <+/-points>}, ...]
    for the top_k most influential features of a single-row prediction.
    """
    try:
        X = feat_row[feature_cols] if hasattr(feat_row, "__getitem__") else feat_row

        if kind == "catboost":
            from catboost import Pool
            sv = model.get_feature_importance(Pool(X), type="ShapValues")
            values = np.asarray(sv)[0][:-1]  # last column = expected value
        else:
            import shap
            explainer = shap.TreeExplainer(model)
            sv = explainer.shap_values(X)
            arr = np.asarray(sv)
            values = arr[0] if arr.ndim > 1 else arr

        pairs = [
            (feat, float(val))
            for feat, val in zip(feature_cols, values)
            if abs(val) > 0.05
        ]
        pairs.sort(key=lambda kv: abs(kv[1]), reverse=True)
        return [{"feature": f, "impact": round(v, 2)} for f, v in pairs[:top_k]]
    except Exception as e:
        print(f"[WARN] SHAP computation failed ({kind}): {e}")
        return []


def pretty_feature(name: str) -> str:
    """Humanizes an engineered feature name for natural-language output."""
    s = name
    for suffix, label in (
        ("_lag1", " (last match)"),
        ("_lag2", " (2 matches ago)"),
        ("_roll3", " (3-match rolling avg)"),
        ("_roll5", " (5-match rolling avg)"),
        ("_pct", " %"),
    ):
        if s.endswith(suffix):
            s = s[: -len(suffix)] + label
            break
    return s.replace("_", " ").strip()
