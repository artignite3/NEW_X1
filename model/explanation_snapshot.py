"""Persist only JSON data and computed attributions, never pickled model objects."""
from intelligence.shap_explainer import top_shap_features, top_shap_features_ensemble


def create_snapshot(cached):
    drivers = {}
    details = cached.get("details")
    if details:
        for key in cached["selected"]:
            row = details["features"].get(key)
            if row is None:
                continue
            drivers[key] = (top_shap_features(details["model"], row, details["feature_cols"], "catboost")
                           if cached["fmt"] == "t20" else top_shap_features_ensemble(details["model"], row, details["feature_cols"]))
    return {**{key: value for key, value in cached.items() if key != "details"}, "drivers": drivers}
