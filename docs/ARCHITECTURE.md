# NEW_X1 — Architecture & Technical Design

## 1. System Overview
NEW_X1 is an expert Cricket Performance Intelligence Platform designed to predict individual player performance for upcoming matches across all three formats (T20, ODI, Test) and assemble optimal 11-player lineups.

```
+-------------------------------------------------------------------------+
|                               DATA TIER                                 |
|  Cricsheet Historical Ball-by-Ball Data -> 140 Features per Player-Match|
|  Strict Time-Shift: .shift(1) with Training Cap <= 2025-06-30           |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                              MODEL TIER                                 |
|  - T20 Format: CatBoostRegressor (MAE loss, Native Categoricals)        |
|  - ODI Format: TriBE Stacking Ensemble (CatBoost + LightGBM -> Meta LR) |
|  - Test Format: TriBE Multi-Innings Ensemble (5-day hauled models)      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                          INTELLIGENCE TIER                              |
|  - Real-time News & Injury Detection (Google News RSS + Local Ollama)   |
|  - Pitch Adjustment Factor (PAF for Flat, Seaming, Turning Surfaces)    |
|  - Open-Meteo Environmental Weather (Dew Risk, Overcast Swing Index)     |
|  - 80% Confidence Interval Estimation & Captaincy Upside Metric         |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                         OPTIMIZATION TIER                               |
|  PuLP Integer Linear Programming (CBC Solver)                           |
|  Max: sum(Score[i] - lambda * Var[i]) * x[i]                            |
|  Subject to: 11 Players, 1-5 WK, 1-6 BAT, 2-5 BOWL, 0-5 AR, Team Limits |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                         PRESENTATION TIER                               |
|  - Product UI (Port 8501): Tactical SVG Pitch, Cards, AI Insights       |
|  - Model Evaluation UI (Port 8502): Out-of-Sample Diagnostics, CSVs     |
|  - FastAPI Backend (Port 8000): Modular REST Endpoints                  |
+-------------------------------------------------------------------------+
```

---

## 2. Directory Hierarchy

```
NEW_X1/
|-- data/
|   |-- raw/                    # Cricsheet JSON archives and raw ball-by-ball data
|   |-- interim/                # Intermediate match records and player stats
|   `-- processed/              # 140-feature datasets (.csv and .parquet)
|
|-- data_processing/            # Core feature engineering & data download pipelines
|   |-- data_download.py        # Cricsheet bulk download & people.csv registry
|   `-- feature_engineering.py  # Vectorized time-series & context feature engine
|
|-- model/                      # ML models, training, prediction & solvers
|   |-- train_model.py          # Unified model trainer (CatBoost & TriBE)
|   |-- predict_model.py        # Sub-second squad predictor & evaluator
|   |-- heuristic_solver.py     # PuLP ILP team optimizer with role constraints
|   |-- model_fastapi.py        # REST API endpoints (Port 8000)
|   |-- squads_fastapi.py       # Squad retrieval endpoint (Port 3001)
|   `-- aggregate_stats_fastapi.py # Career analytics & LLM explanation endpoint
|
|-- model_artifacts/            # Saved trained model binaries
|   |-- ProductUI_Model         # T20 CatBoost binary (exact name required)
|   |-- ProductUI_Model_meta.pkl# Feature metadata mapping
|   |-- tribe_odi.pkl           # ODI Stacking Ensemble binary
|   `-- tribe_test.pkl          # Test Stacking Ensemble binary
|
|-- intelligence/               # Contextual intelligence differentiators
|   |-- injury_detector.py      # RSS news scanner, LLM status & availability
|   |-- weather_fetcher.py      # Open-Meteo weather client & swing index
|   `-- pitch_analyzer.py       # Venue PAF score & surface classification
|
|-- UI/                         # User interfaces
|   |-- product_ui.py           # Streamlit Product UI (Port 8501)
|   |-- model_ui.py             # Streamlit Model Evaluation UI (Port 8502)
|   `-- components/
|       `-- cricket_field.py    # Tactical SVG pitch visualizer
|
|-- outputs/                    # Exported evaluation CSVs & diagnostic artifacts
|-- out_of_sample_data/         # Drop directory for external test match evaluations
|-- run_all.py                  # Universal single-terminal service launcher
|-- run_all.bat                 # Windows one-click batch launcher
|-- requirements.txt            # Pinned production dependencies
`-- README.md                   # Quickstart and usage manual
```
