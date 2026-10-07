"""
NEW_X1 — Cricket Intelligence API (v2)

Endpoints:
  GET  /health                 -> service + model availability
  GET  /matches                -> upcoming fixtures
  GET  /match_squads           -> normalized, name-resolved squads for a fixture
  GET  /teams                  -> known team names (Custom Simulator datalist)
  GET  /venues                 -> known venues (Custom Simulator datalist)
  POST /generate_best_team     -> predicted + optimized Optimal XI
  POST /explain_team           -> SHAP drivers + Ollama analyst report

Run:  uvicorn model.model_fastapi:app --host 0.0.0.0 --port 8000
"""

import os
import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.team_generator import (  # noqa: E402
    _EXPLAIN_CACHE,
    generate_best_team,
    get_fantasy,
    get_match_info,
    get_matches_json,
    get_resolver,
    normalize_format,
    pool_from_match_squads,
    validate_date,
)

app = FastAPI(title="NEW_X1 Cricket Intelligence API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# GET endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
def home():
    return {
        "message": "NEW_X1 Cricket Intelligence API",
        "docs": "/docs",
        "version": "2.0",
    }


@app.get("/health")
def health():
    """Model availability + Ollama reachability, for the UI status bar."""
    models = {}
    from model.predict_model import get_model
    for fmt in ("t20", "odi", "test"):
        try:
            get_model(fmt)
            models[fmt] = True
        except Exception:
            models[fmt] = False

    ollama_ok = False
    try:
        import ollama
        ollama.list()
        ollama_ok = True
    except Exception:
        ollama_ok = False

    return {"status": "ok", "models": models, "ollama": ollama_ok}


@app.get("/matches")
def matches():
    """All known upcoming fixtures (client filters by date)."""
    return {"matches": get_matches_json()}


@app.get("/match_squads")
def match_squads(match_id: str):
    """Normalized squads for a fixture, with roles and name-resolution preview."""
    match = get_match_info(match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    fmt = normalize_format(match.get("match_type", "t20"))
    try:
        pool, meta = pool_from_match_squads(match_id, fmt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    resolver = get_resolver(fmt)

    def player_out(p):
        key, method = resolver.resolve(p["display_name"])
        return {
            "display_name": p["display_name"],
            "fantasy_key": key,
            "name_match": method,
            "role": p["role"],
            "injury_status": p["injury_status"],
            "team": p["team"],
        }

    squads = meta["squads"]
    return {
        "match_id": str(match_id),
        "team1": squads["team1_name"],
        "team2": squads["team2_name"],
        "venue": meta["venue"],
        "date": meta["date"],
        "format": fmt,
        "team1_squad": [player_out(p) for p in squads["team1"]],
        "team2_squad": [player_out(p) for p in squads["team2"]],
    }


@app.get("/teams")
def teams():
    """Distinct team names known to the platform (for the Custom Simulator)."""
    names = set()
    for m in get_matches_json():
        if m.get("team1"):
            names.add(m["team1"])
        if m.get("team2"):
            names.add(m["team2"])

    from model.team_generator import _build_datewise_index, _norm_team
    for key in _build_datewise_index():
        names.add(key.title())

    venues = sorted({m.get("venue") for m in get_matches_json() if m.get("venue")})
    return {"teams": sorted(n for n in names if n), "venues": venues}


@app.get("/venues")
def venues():
    return {"venues": sorted({m.get("venue") for m in get_matches_json() if m.get("venue")})}


# ─────────────────────────────────────────────────────────────────────────────
# POST endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/generate_best_team")
def generate_best_team_endpoint(request_data: dict):
    try:
        return generate_best_team(request_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Team generation failed: {e}")


@app.post("/explain_team")
def explain_team(request_data: dict):
    """
    SHAP feature drivers + natural-language analyst report (local Ollama).
    Body: {"explain_token": "<token from /generate_best_team response>"}
    """
    token = request_data.get("explain_token")
    if not token or token not in _EXPLAIN_CACHE:
        raise HTTPException(
            status_code=404,
            detail="Explain token not found or expired. Re-run /generate_best_team.",
        )

    cached = _EXPLAIN_CACHE[token]
    from intelligence.shap_explainer import top_shap_features
    from intelligence.llm_analyst import generate_team_report

    details = cached.get("details")
    drivers_by_player: dict = {}

    if details and cached["fmt"] == "t20":
        # T20: single CatBoost model
        for key, feat_row in details["features"].items():
            drivers_by_player[key] = top_shap_features(
                details["model"], feat_row, details["feature_cols"], "catboost"
            )
    elif details:
        # TriBE: explain with the strongest base learner
        base_models = details["model"].get("base_models", {})
        preferred = next(
            (n for n in ("catboost", "xgboost", "lightgbm") if n in base_models), None
        )
        if preferred:
            for key, feat_row in details["features"].items():
                drivers_by_player[key] = top_shap_features(
                    base_models[preferred], feat_row, details["feature_cols"], preferred
                )

    report = generate_team_report(
        cached=cached,
        drivers_by_player=drivers_by_player,
    )
    return report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
