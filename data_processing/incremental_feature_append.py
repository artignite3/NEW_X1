#!/usr/bin/env python3
"""
NEW_X1 — Incremental Feature Update (Stage 2)
Reads the latest JSON, identifies new match rows not present in features_*.parquet,
computes their TS features using historical expanding contexts, and appends to parquet.
Updates Train/Test splits using a dynamic cutoff (Today - 1 day).
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

import json
import logging
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import numpy as np
from tqdm import tqdm

from feature_engineering import flatten_json, add_ts_features, add_context_features, FORMATS, DATA_PROCESSED

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

# Cutoff is now dynamic: everything up to yesterday is Train/Eval, future is not mixed.
DYNAMIC_TEST_CUTOFF = str(date.today() - timedelta(days=1))
STRICT_TRAIN_CUTOFF = "2025-06-30"

def incremental_update(fmt: str, json_path: Path):
    logger.info(f"=== Incremental Update: {fmt.upper()} ===")
    parquet_path = DATA_PROCESSED / f"features_{fmt}.parquet"
    out_csv = DATA_PROCESSED / f"features_{fmt}.csv"
    train_out = DATA_PROCESSED / f"train_{fmt}.csv"
    test_out = DATA_PROCESSED / f"test_{fmt}.csv"
    
    if not parquet_path.exists():
        logger.warning(f"{parquet_path.name} not found. Suggest running full feature_engineering.py first.")
        return
        
    logger.info(f"Loading existing {parquet_path.name}...")
    df_existing = pd.read_parquet(parquet_path)
    if not pd.api.types.is_datetime64_any_dtype(df_existing["match_date"]):
        df_existing["match_date"] = pd.to_datetime(df_existing["match_date"])
        
    existing_keys = set(df_existing["player"].astype(str) + "_" + df_existing["match_key"].astype(str))
    
    df_new_raw = flatten_json(json_path, fmt)
    new_keys = df_new_raw["player"].astype(str) + "_" + df_new_raw["match_key"].astype(str)
    
    missing_mask = ~new_keys.isin(existing_keys)
    if not missing_mask.any():
        logger.info("No new matches found in JSON to append.")
        train = df_existing[df_existing["match_date"] <= pd.Timestamp(STRICT_TRAIN_CUTOFF)]
        test = df_existing[(df_existing["match_date"] > pd.Timestamp(STRICT_TRAIN_CUTOFF)) & 
                           (df_existing["match_date"] <= pd.Timestamp(DYNAMIC_TEST_CUTOFF))]
        
        train.to_csv(train_out, index=False)
        test.to_csv(test_out, index=False)
        logger.info(f"Updated Splits | Train (≤{STRICT_TRAIN_CUTOFF}): {len(train):,} | Test (≤{DYNAMIC_TEST_CUTOFF}): {len(test):,}")
        return

    logger.info(f"Found {missing_mask.sum()} new player-match records. Computing features incrementally...")
    
    df_full = add_ts_features(df_new_raw)
    df_full = add_context_features(df_full)
    
    df_full = df_full.dropna(subset=["total_points_lag1"])
    df_full = df_full.replace([np.inf, -np.inf], 0)
    
    df_full.to_parquet(parquet_path, engine="pyarrow")
    df_full.to_csv(out_csv, index=False)
    logger.info(f"Saved updated {parquet_path.name}")
    
    train = df_full[df_full["match_date"] <= pd.Timestamp(STRICT_TRAIN_CUTOFF)]
    test = df_full[(df_full["match_date"] > pd.Timestamp(STRICT_TRAIN_CUTOFF)) & 
                       (df_full["match_date"] <= pd.Timestamp(DYNAMIC_TEST_CUTOFF))]
                       
    train.to_csv(train_out, index=False)
    test.to_csv(test_out, index=False)
    
    logger.info(f"Updated Splits | Train (≤{STRICT_TRAIN_CUTOFF}): {len(train):,} | Test (≤{DYNAMIC_TEST_CUTOFF}): {len(test):,}")

def main():
    logger.info("NEW_X1 — Stateful Incremental Feature Update")
    logger.info(f"Dynamic Test Cutoff: {DYNAMIC_TEST_CUTOFF}")
    
    for fmt, path in FORMATS.items():
        if path.exists():
            incremental_update(fmt, path)
            
    logger.info("Incremental feature engineering complete.")

if __name__ == "__main__":
    main()
