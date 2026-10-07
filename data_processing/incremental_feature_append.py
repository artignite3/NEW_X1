"""Update only changed players' time-series features; refresh context and splits.

Backfills/corrections rebuild the affected players' complete history to preserve
EMA and cumulative statistics exactly. Context averages are inexpensive to
recompute across the combined dataset. A schema migration rebuilds all rows.
"""
import logging
from datetime import date, timedelta
import numpy as np
import pandas as pd
from feature_engineering import (flatten_json, add_ts_features, add_context_features,
    FORMATS, DATA_PROCESSED, RAW_STATS, TRAIN_CUTOFF, FEATURE_SCHEMA_VERSION)

logging.basicConfig(level=logging.INFO)


def incremental_update(fmt, json_path):
    path = DATA_PROCESSED / f"features_{fmt}.parquet"
    raw = flatten_json(json_path, fmt)
    previous = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    current = (not previous.empty and "feature_schema_version" in previous
               and previous.feature_schema_version.eq(FEATURE_SCHEMA_VERSION).all())
    if current:
        keys = ["player", "match_key"]
        columns = keys + ["match_date", "available_date", "venue", "opponent", "total_points"] + RAW_STATS
        old = previous[columns].copy()
        new = raw[columns].copy()
        comparison = old.merge(new, on=keys, how="outer", suffixes=("_old", "_new"), indicator=True)
        changed = comparison["_merge"].ne("both")
        for column in columns[len(keys):]:
            left, right = comparison[column + "_old"], comparison[column + "_new"]
            changed |= ~(left.eq(right) | (left.isna() & right.isna()))
        players = set(comparison.loc[changed, "player"])
        if players:
            rebuilt = add_ts_features(raw[raw.player.isin(players)].reset_index(drop=True))
            combined = pd.concat([previous[~previous.player.isin(players)], rebuilt], ignore_index=True)
        else:
            combined = previous
        logging.info("%s: recomputed %s changed players", fmt, len(players))
    else:
        combined = add_ts_features(raw)
        logging.info("%s: initial/schema rebuild", fmt)
    combined = add_context_features(combined.sort_values(["player", "match_date", "match_key"]).reset_index(drop=True))
    combined = combined.replace([np.inf, -np.inf], 0)
    # Atomic publication keeps API readers away from partial files.
    for name, frame in (("features", combined),
                        ("train", combined[(combined.match_date <= TRAIN_CUTOFF) & (combined.available_date <= TRAIN_CUTOFF)]),
                        ("test", combined[(combined.match_date > TRAIN_CUTOFF) & (combined.available_date <= pd.Timestamp(date.today() - timedelta(days=1)))])):
        destination = DATA_PROCESSED / f"{name}_{fmt}.csv"
        temporary = destination.with_suffix(".csv.tmp")
        frame.to_csv(temporary, index=False)
        temporary.replace(destination)
    temporary = path.with_suffix(".parquet.tmp")
    combined.to_parquet(temporary, index=False)
    temporary.replace(path)


def main():
    for fmt, path in FORMATS.items():
        if not path.exists():
            raise FileNotFoundError(path)
        incremental_update(fmt, path)


if __name__ == "__main__":
    main()
