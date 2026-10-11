# Saved model artifacts

The T20 CatBoost file `ProductUI_Model` (with its metadata) and ODI/Test `tribe_*.pkl` ensembles are loaded by [`model/predict_model.py`](../model/predict_model.py). `*_metrics.json` holds evaluation evidence, and `archive/` keeps earlier binaries for recovery. The source checkout may contain only metrics or archived files; use `NEW_X1_MODEL_ROOT` or `run_all.py --artifacts-root` to select a complete trusted artifact checkout.

Never load model pickle/joblib files from an untrusted source. The prediction loader validates expected schema/cutoff metadata, and the local backup path is checked by resilience tests. Do not delete archives as routine cleanup. See the [model guide](../model/README.md) and [runbook](../docs/RUNBOOK.md).
