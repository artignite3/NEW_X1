"""Validate an isolated release in a fresh process before any pickle is served.

Only trusted private storage writers may supply artifacts: joblib files are code.
"""
import argparse
import json
import os
from pathlib import Path


def validate_feature_frame(frame, cols):
    import numpy as np
    import pandas as pd
    from model.data_contract import FEATURE_SCHEMA_VERSION
    from data_processing.feature_engineering import RAW_STATS
    required = set(cols) | set(RAW_STATS) | {"player", "match_key", "match_date", "available_date",
        "feature_schema_version", "venue", "opponent", "total_points"}
    if frame.empty or not required.issubset(frame) or not frame.feature_schema_version.eq(FEATURE_SCHEMA_VERSION).all():
        raise ValueError("Feature schema incomplete")
    for column in ("player", "match_key"):
        if not frame[column].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise ValueError("Feature identity is missing")
    dates = pd.to_datetime(frame.match_date, errors="raise")
    available = pd.to_datetime(frame.available_date, errors="raise")
    if dates.isna().any() or available.isna().any() or (available < dates).any():
        raise ValueError("Invalid availability dates")
    # Lag/rolling values are absent for cold-start rows. Inference fills these
    # values with zero; infinite values and invalid numeric types are rejected.
    matrix = frame[cols].to_numpy(dtype=float)
    if np.isinf(matrix).any(): raise ValueError("Infinite model features")
    if not np.isfinite(frame.total_points.to_numpy(dtype=float)).all(): raise ValueError("Invalid target values")
    return dates


def validate(root):
    import numpy as np
    import pyarrow.parquet as pq
    root = Path(root).resolve()
    os.environ["NEW_X1_DATA_ROOT"] = str(root / "data")
    os.environ["NEW_X1_MODEL_ROOT"] = str(root / "model_artifacts")
    from model.predict_model import load_model, tribe_predict
    from data.future_matches.fixture_store import read_valid as read_fixtures
    from data.future_matches.squad_store import read_valid as read_squads
    summary = {}
    for fmt in ("t20", "odi", "test"):
        kind, model, cols = load_model(fmt, allow_backup=False)
        parquet = pq.ParquetFile(root / "data" / "processed" / f"features_{fmt}.parquet")
        seen, rows, latest = set(), 0, None
        for batch in parquet.iter_batches(batch_size=5000):
            frame = batch.to_pandas()
            dates = validate_feature_frame(frame, cols)
            keys = list(zip(frame.player, frame.match_key))
            if len(set(keys)) != len(keys) or seen.intersection(keys): raise ValueError("Duplicate feature rows")
            seen.update(keys)
            rows += len(frame)
            latest = max(latest, dates.max()) if latest is not None else dates.max()
            sample = frame[cols].iloc[:1].fillna(0)
            predictions = model.predict(sample) if kind == "catboost" else tribe_predict(model, sample)
            if not np.isfinite(predictions).all(): raise ValueError("Model prediction is non-finite")
        if not rows: raise ValueError("Empty feature history")
        del frame, batch, seen, model
        with (root / "data" / "processed" / f"player_fantasy_points_{fmt}.json").open(encoding="utf-8") as handle:
            fantasy = json.load(handle)
        if not isinstance(fantasy, dict) or not fantasy: raise ValueError("Empty fantasy history")
        for player, matches in fantasy.items():
            if not isinstance(player, str) or not player or not isinstance(matches, dict) or not matches:
                raise ValueError("Invalid player history")
            for record in matches.values():
                if not isinstance(record, dict) or not np.isfinite(float(record.get("total_points", float("nan")))):
                    raise ValueError("Invalid fantasy points")
        summary[fmt] = {"rows": rows, "players": len(fantasy), "latest_match": latest.date().isoformat()}
        del fantasy
    fixtures = read_fixtures(root / "data/future_matches/upcoming_matches.json")
    squads = read_squads(root / "data/future_matches/upcoming_squads.json")
    summary["fixtures_fetched_at"] = fixtures["fetched_at"]
    summary["squads_fetched_at"] = squads["fetched_at"]
    venue_path = root / "data" / "venue_history.json"
    if venue_path.exists():
        from intelligence.venue_history import validate_snapshot
        with venue_path.open(encoding="utf-8") as handle:
            history = validate_snapshot(json.load(handle))
        summary["venue_history_matches"] = len(history["matches"])
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    print(json.dumps(validate(parser.parse_args().root), allow_nan=False))


if __name__ == "__main__": main()
