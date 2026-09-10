# NEW_X1 — Cricket Performance Intelligence Platform

> Predicts individual player performance for upcoming cricket matches (T20, ODI, Test)  
> Expert analyst tool — not a fantasy sports app.

---

## Quick Start

### 1. Prerequisites
- Python 3.10 or 3.11
- [Ollama](https://ollama.com) installed locally

### 2. Environment Setup
```bash
python -m venv env
env\Scripts\activate          # Windows
pip install -r requirements.txt

# Pull local LLM
ollama pull llama3.2:3b
```

### 3. Configure API Keys
```bash
copy .env.example .env
# Edit .env — add your cricketdata.org key
```

### 4. Generate Feature Data (one-time)
```bash
python data_processing/feature_engineering.py
```

### 5. Train Models
```bash
python model/train_model.py
# Creates: model_artifacts/ProductUI_Model  (T20 CatBoost)
#          model_artifacts/tribe_odi.pkl
#          model_artifacts/tribe_test.pkl
```

### 6. Run Services (4 terminals)
```bash
# Terminal 1 — Main API
cd model && uvicorn model_fastapi:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Squads API
cd model && uvicorn squads_fastapi:app --host 0.0.0.0 --port 3001 --reload

# Terminal 3 — Product UI  (http://localhost:8501)
streamlit run UI/product_ui.py --server.port 8501

# Terminal 4 — Model UI  (http://localhost:8502)
streamlit run UI/model_ui.py --server.port 8502

# Terminal 5 — Ollama (keep running)
ollama serve
```

---

## Architecture

```
Cricsheet JSONs → Feature Engineering → Train (CatBoost / TriBE)
                                           ↓
                                    FastAPI (port 8000)
                                    ├─ /generate_best_team
                                    ├─ /analyze_player
                                    └─ /analyze_team
                                           ↓
                          ┌────────────────┴──────────────────┐
                   Product UI (8501)                   Model UI (8502)
                   Team1 + Team2 + Date                Train/Test dates
                   → Top 11 performers                 → MAE CSV export
                   → SHAP + LLM explain
```

## Port Map

| Service | Port |
|---|---|
| FastAPI — predictions | 8000 |
| FastAPI — squads | 3001 |
| Streamlit Product UI | 8501 |
| Streamlit Model UI | 8502 |
| Ollama local LLM | 11434 |

## Models

| Format | Model | Notes |
|---|---|---|
| T20 | CatBoostRegressor | `model_artifacts/ProductUI_Model` |
| ODI | TriBE Ensemble | `model_artifacts/tribe_odi.pkl` |
| Test | TriBE Ensemble | `model_artifacts/tribe_test.pkl` |

TriBE = CatBoost + XGBoost + LightGBM → LinearRegression meta-model (OOF stacking)

## Data

- Source: [cricsheet.org](https://cricsheet.org) — ball-by-ball JSON
- Training window: **2010-01-01 to 2025-06-30**
- Testing window: **2025-07-01 to 2026-06-30**
- Formats: T20, ODI, Test (international + domestic)

## Hard Rules

1. Training data strictly `≤ 2025-06-30` (No future data leakage)
2. `model_artifacts/ProductUI_Model` — exact name, no extension
3. Product UI response `≤ 10 seconds`
4. MAE CSV must be reproducible with same inputs

