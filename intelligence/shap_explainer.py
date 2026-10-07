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


_EXPLAINERS = {}


def _raw_shap_values(model, feat_row, feature_cols, kind):
    """Return every unrounded feature contribution for one base learner."""
    X = feat_row[feature_cols]
    if kind == "catboost":
        from catboost import Pool
        values = np.asarray(model.get_feature_importance(Pool(X), type="ShapValues"), dtype=float)[0, :-1]
    else:
        import shap
        key = id(model)
        if key not in _EXPLAINERS:
            _EXPLAINERS[key] = shap.TreeExplainer(model)
        values = np.asarray(_EXPLAINERS[key].shap_values(X), dtype=float).reshape(-1)
    if values.shape != (len(feature_cols),) or not np.isfinite(values).all():
        raise ValueError(f"Incomplete {kind} attribution")
    return values


def _top(values, feature_cols, top_k):
    indices = np.argsort(-np.abs(values))[:top_k]
    return [{"feature": feature_cols[int(i)], "impact": round(float(values[i]), 2)}
            for i in indices if abs(values[i]) > 0.05]


def top_shap_features(model, feat_row, feature_cols: List[str], kind: str = "catboost",
                      top_k: int = 3) -> List[dict]:
    try:
        return _top(_raw_shap_values(model, feat_row, feature_cols, kind), feature_cols, top_k)
    except Exception as error:
        print(f"[WARN] SHAP computation failed ({kind}): {error}")
        return []


def top_shap_features_ensemble(bundle: dict, feat_row, feature_cols: List[str],
                               top_k: int = 3) -> List[dict]:
    """Sum full base-model SHAP vectors under the trained linear meta weights.

    If even one base attribution fails, decline to report partial drivers.
    The linear intercept affects the baseline, not each feature's impact.
    """
    try:
        names = bundle["base_model_names"]
        weights = np.asarray(bundle["meta_model"].coef_, dtype=float).reshape(-1)
        if len(names) != len(weights) or not np.isfinite(weights).all():
            raise ValueError("Ensemble weights do not match base models")
        combined = np.zeros(len(feature_cols))
        for name, weight in zip(names, weights):
            combined += weight * _raw_shap_values(bundle["base_models"][name], feat_row, feature_cols, name)
        return _top(combined, feature_cols, top_k)
    except Exception as error:
        print(f"[WARN] Ensemble SHAP unavailable: {error}")
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
