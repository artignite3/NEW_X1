# NEW_X1 — Runbook

All commands run from the repo root on Windows (Git Bash). Python: `env/Scripts/python.exe`.

## 0. Setup (clean machine)
```bash
python -m venv env
env/Scripts/python.exe -m pip install -r requirements.txt
cd frontend && npm install && cd ..
copy .env.example .env        # then fill CRICKET_DATA_API_KEY / RAPID_API_KEY
ollama pull llama3.2:3b       # optional — AI analyst (heuristic fallback without it)
```

## 1. Data pipeline (Cricsheet → features)
```bash
# Full nightly sync: download → ingest → incremental features → fixture refresh
env/Scripts/python.exe run_daily_sync.py

# Individual stages
env/Scripts/python.exe data_processing/data_download.py
env/Scripts/python.exe data_processing/cricsheet_ingestor.py
env/Scripts/python.exe data_processing/incremental_feature_append.py
```
Outputs: `data/processed/player_fantasy_points_{t20,odi,test}.json`,
`features_{fmt}.parquet`, `train_{fmt}.csv` / `test_{fmt}.csv`,
`ingestion_{fmt}.json` (provenance manifests).
Ingestion is manifest-based: unchanged players are skipped, changed players are
recomputed. Re-running without new data must not change outputs (see ISSUES #5).

## 2. Fixtures & squads (Cricbuzz via RapidAPI)
```bash
env/Scripts/python.exe data/future_matches/schedule_fetcher.py            # 7-day fixtures (~3 calls)
env/Scripts/python.exe data/future_matches/squad_fetcher.py               # all matches (heavy!)
env/Scripts/python.exe data/future_matches/squad_fetcher.py --ids 151576,151587   # quota-aware
env/Scripts/python.exe data/future_matches/cricapi_sync.py --days 2       # free-tier fallback (imminent only)
```
Quota: 200 requests/month on the free RapidAPI plan — prefer `--ids`.

## 3. Training (schema-gated)
```bash
env/Scripts/python.exe model/train_model.py            # trains formats whose datasets are v2
# Artifacts: model_artifacts/ProductUI_Model (T20), tribe_{odi,test}.pkl
# Refuses to train if features lack feature_schema_version=2 or exceed the cutoff
```
Before retraining a format, archive the current artifact:
```bash
mkdir -p model_artifacts/archive/$(date +%F) && cp model_artifacts/{tribe_odi.pkl,tribe_test.pkl,ProductUI_Model,ProductUI_Model_meta.pkl} model_artifacts/archive/$(date +%F)/ 2>/dev/null || true
```

## 4. Evaluation
```bash
env/Scripts/python.exe model/predict_model.py --mode eval --format odi \
    --test-start 2025-07-01 --test-end 2026-10-06 --output-csv eval_odi.csv
```
Outputs land in `outputs/`. Evaluation is chronological; whole matches are kept
together. See docs/ISSUES.md #2 for the validation contract.

## 5. Tests
```bash
env/Scripts/python.exe tests/test_correctness.py        # 11 regression tests (M0 green)
env/Scripts/python.exe -m py_compile model/*.py data_processing/*.py intelligence/*.py
```

## 6. Launch / stop
```bash
run_all.bat          # backend :8000 + Next.js :3000 + model UI :8502; Ctrl+C stops all
# Manual:
env/Scripts/python.exe -m uvicorn model.model_fastapi:app --host 127.0.0.1 --port 8000
cd frontend && npx next dev --port 3000
```
Verify: `curl http://localhost:8000/health` (models t20/odi/test + ollama),
`curl http://localhost:8000/matches | head`. If a port is stuck:
`netstat -ano | grep :8000` → `taskkill //F //PID <pid>`.

## 7. Rollback
- Code: `git checkout main` (main = last gated release; work happens on `dev`).
- Models: restore from `model_artifacts/archive/<date>/`.
- Data: re-run §1 (regenerable); fixtures/squads re-run §2.
