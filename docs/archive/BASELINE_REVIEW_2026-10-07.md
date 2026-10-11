# M0 — Baseline Review (2026-10-07)

Historical baseline snapshot. See the [current documentation index](../README.md) for live deployment and operating guides.

Status: **GATE PASSED** — verified working tree, green correctness suite, artifact
archive, documented runbook. No model is labelled "validated" — see ISSUES_2026-10-07.md #2.

## 1. Process state at review time

| Item | State |
|---|---|
| Backend (uvicorn :8000) | Single instance, PID from latest start; serving reviewed working tree |
| Frontend (next dev :3000) | Single instance |
| Streamlit model UI (:8502) | Not running |
| Ollama (:11434) | Not running — explanations use heuristic fallback |
| Zombie processes | 1 duplicate uvicorn found and terminated during review |

## 2. Change inventory (uncommitted work reconciled this review)

All changes below were left uncommitted by the parallel v2 workstream. Each file
was byte-compiled (19/19 OK), the project test suite ran green (11/11), and the
frontend production build succeeded before committing to `dev`.

**A. Data-contract / leakage-controls (user workstream) — verified, committed**
| File | Change | Evidence |
|---|---|---|
| `model/data_contract.py` (new) | `FEATURE_SCHEMA_VERSION=2`, `TRAIN_CUTOFF=2025-06-30` | imported by predictor & trainer |
| `model/train_model.py` | Schema-version gate; hard cutoff enforced on `match_date` AND `available_date`; `career_*` features excluded from training; TimeSeriesSplit validation | unit tests; T20+ODI retrains pass guard |
| `model/predict_model.py` | Model metadata validator (rejects pre-v2 artifacts); mtime-stamped model/dataset caches; `build_request_features` for upcoming matches | guard rejects old Test bundle (expected) |
| `data_processing/feature_engineering.py` | `available_date` semantics; schema stamping; chronological feature computation | tests |
| `data_processing/incremental_feature_append.py`, `cricsheet_ingestor.py`, `data_download.py` | Manifest-based ingestion (`data/processed/ingestion_*.json`), recompute-changed-players only | manifests written 15:14 |
| `model/calculator_test.py` | Test-format scoring updates | tests cover scoring |
| `intelligence/*` | `weather_multiplier` (style-aware, date-aware forecast), `pitch_multiplier`, injury detector updates | tests cover multipliers |
| `model/team_generator.py` | mtime cache invalidation, multiplier integration, fresh squad/matches reads | live end-to-end runs |
| `model/model_fastapi.py` | degraded-health reporting, explain-token expiry, truthful `has_squad`, richer `/teams` | live endpoints verified |
| `model/llm_inference.py`, `UI/model_ui.py`, `run_all.*` | minor consistency updates | compiled |

**B. Frontend tweaks (user) — verified, committed**
`page.tsx`, `simulator/page.tsx`, `FixturesBoard.tsx` (+scan-news toggle),
`AnalysisResult.tsx`, `IntelligencePanels.tsx`, `PlayerCard.tsx`, `api.ts`,
`types.ts` — production build passes.

**C. My fixes already on `main`** — squad fetcher merge/--ids, truthful
`has_squad`, fixture/squad backfill (commits c65ebf1, 7e6f4c9).

**D. Provisional / not committed**
| Item | Reason |
|---|---|
| `data/processed/train_t20.csv.tmp`, `test_t20.csv.tmp` | transient pipeline temps; gitignored |
| `catboost_info/` | CatBoost training byproduct; gitignored |
| `data/processed/ingestion_*.json` | committed as provenance manifests |

## 3. Artifact inventory

| Artifact | Built | Schema | Guard | Recoverable copies |
|---|---|---|---|---|
| `ProductUI_Model` (+meta) — T20 | 10-07 15:12 | v2 | PASS | archived copy |
| `tribe_odi.pkl` — ODI | 10-07 15:17 | v2 | PASS | archived copy |
| `tribe_test.pkl` — Test | 09-10 (Sep 10) | pre-v2 | **REJECTED (expected)** | archived copy |
| `t20_metrics.json` / `odi_metrics.json` | 10-07 15:12/15:17 | — | — | in git history |
| `features_t20/odi.parquet` | 10-07 (v2 rebuild) | v2 | — | not recoverable (overwritten in place) |
| `player_fantasy_points_*.json` | 10-07 (ingestion manifests) | v1 data | — | regenerable via runbook |

Archive location: `model_artifacts/archive/2026-10-07_pre-v2/` (local only;
binaries are gitignored). **Rollback path:** restore archived binaries +
`git checkout main` for code.

## 4. Test evidence

- `python tests/test_correctness.py` → **11/11 OK** (2.4s) — covers TS features,
  ingestion record parsing, Test scoring, solver/constraints, covariance,
  weather/pitch multipliers, model metadata validation.
- `python -m py_compile` → 19/19 modified Python files OK.
- `next build` → success (all routes).
- Live end-to-end (this review): India vs West Indies T20I XI generated on v2
  CatBoost with date-aware weather; Australia Champions XI generated after squad
  backfill; truthful squad status 24/31.
