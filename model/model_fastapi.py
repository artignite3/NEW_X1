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
import threading
import time
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Path as APIPath, Query
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.team_generator import (  # noqa: E402
    _EXPLAIN_CACHE,
    _fantasy_history_stamp,
    generate_best_team,
    get_datewise_json,
    get_fantasy,
    get_match_info,
    get_matches_json,
    get_resolver,
    last_match_squads_for_fixture,
    normalize_format,
    pool_from_match_squads,
    resolve_match_squad_entry,
    validate_date,
)

from pipeline.serving import runtime_guard, public_status, STATE, release_is_fresh  # noqa: E402
app = FastAPI(title="NEW_X1 Cricket Intelligence API", version="2.0", dependencies=[Depends(runtime_guard)])
from model.api_schemas import GenerateRequest, ExplainRequest, SaveAnalysisRequest  # noqa: E402
from model.auth import Principal, require_user, auth_config  # noqa: E402
from model.user_store import UserStore  # noqa: E402
from model.explanation_snapshot import create_snapshot  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Venue registry: collapses historical spelling variants of the same ground
# ("Wankhede Stadium" vs "Wankhede Stadium, Mumbai") onto one canonical form.
# Built lazily on first venue call — building scans the fantasy datasets.
from intelligence import venue_registry as _vreg  # noqa: E402

_TEAMS_CACHE: dict = {"stamp": None, "payload": None}


def _build_venue_registry():
    from collections import Counter
    counts = Counter()
    for fmt in ("test", "odi", "t20"):
        try:
            fantasy = get_fantasy(fmt)
        except FileNotFoundError:
            continue
        for matches in fantasy.values():
            for stats in matches.values():
                venue = stats.get("venue")
                if venue:
                    counts[venue] += 1
        del fantasy
    return _vreg.VenueRegistry(counts)


_vreg.configure(_build_venue_registry)


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
    """Lightweight readiness check; large histories load only on analysis."""
    models = {}
    model_sources, feature_sources, fantasy_sources = {}, {}, {}
    from model.predict_model import get_model, _MODEL_SOURCES, _DF_SOURCES, _DF_CACHE
    from model.team_generator import _FANTASY_SOURCES, _FANTASY_CACHE
    for fmt in ("t20", "odi", "test"):
        try:
            get_model(fmt)
            models[fmt] = True
        except Exception:
            models[fmt] = False
        model_sources[fmt] = _MODEL_SOURCES.get(fmt, "unavailable") if models[fmt] else "unavailable"
        feature_sources[fmt] = _DF_SOURCES.get(fmt, "unchecked") if fmt in _DF_CACHE else "unchecked"
        fantasy_sources[fmt] = _FANTASY_SOURCES.get(fmt, "unchecked") if fmt in _FANTASY_CACHE else "unchecked"

    ollama_ok = False
    try:
        from model.llm_inference import ollama_available
        ollama_ok = ollama_available()
    except Exception:
        ollama_ok = False

    from data.future_matches.fixture_store import load
    feed = load()
    from data.future_matches.squad_store import load as load_squads
    squads = load_squads()
    sources = {"models": model_sources, "features": feature_sources, "fantasy": fantasy_sources}
    healthy = (all(models.values()) and all(source == "current" for source in model_sources.values())
               and all(source != "last_good" for group in (feature_sources, fantasy_sources) for source in group.values())
               and not feed["warning"] and not squads["warning"])
    release = public_status()
    healthy = healthy and not release["fallback_used"] and not release["refresh_error"] and release["last_pipeline_status"] not in {"failed", "degraded"}
    return {"status": "ok" if healthy else "degraded", "models": models, "ollama": ollama_ok, "release": release,
            "sources": sources, "data_checked_on_request": True,
            "fixtures": {k: feed[k] for k in ("source", "fetched_at", "fallback_used", "warning")},
            "squads": {k: squads[k] for k in ("fetched_at", "fallback_used", "warning")}}


@app.get("/live")
def live():
    return {"status": "alive"}


@app.get("/ready")
def ready():
    auth_config()  # Raises a controlled 503 for missing/invalid deployed settings.
    if not STATE["release_id"] or not release_is_fresh():
        raise HTTPException(status_code=503, detail="A recent verified artifact release is required")
    return {"status": "ready", "release": public_status()}


@app.get("/matches")
def matches():
    """All known upcoming fixtures (client filters by date).

    Distinguish provider squads from provisional last-match XIs.
    """
    from model.team_generator import get_squads_json

    try:
        squads_json = get_squads_json()
    except FileNotFoundError:
        squads_json = {}

    from data.future_matches.fixture_store import load
    feed = load()
    out = []
    for m in feed["matches"]:
        m = dict(m)
        _entry, squad_source, source_ids = resolve_match_squad_entry(m, squads_json)
        if squad_source != "pending":
            m["squad_source"] = squad_source
            if source_ids:
                m["squad_source_match_ids"] = source_ids
        else:
            try:
                historical = last_match_squads_for_fixture(m, normalize_format(m["match_type"]))
            except (OSError, ValueError, TypeError):
                historical = None
            m["squad_source"] = "last_match" if historical else "pending"
            if historical:
                m["squad_match_dates"] = {m["team1"]: historical["team1"]["date"],
                                          m["team2"]: historical["team2"]["date"]}
        m["has_squad"] = m["squad_source"] != "pending"
        out.append(m)
    return {**feed, "matches": out}


@app.get("/match_squads")
def match_squads(match_id: str = Query(min_length=1, max_length=128), user: Principal = Depends(require_user)):
    # Signed-in only: each call may load a full format history under the shared lock.
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
    gender = "female" if "women" in (match["team1"] + match["team2"]).lower() else "male"

    def player_out(p):
        key, method = resolver.resolve(p["display_name"], require_gender=gender)
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
        "squad_source": meta["squad_source"],
        "squad_source_match_ids": meta.get("squad_source_match_ids"),
        "squad_match_dates": meta.get("squad_match_dates"),
        "team1_squad": [player_out(p) for p in squads["team1"]],
        "team2_squad": [player_out(p) for p in squads["team2"]],
    }


@app.get("/teams")
def teams():
    """Distinct team names + canonical venues (Custom Simulator datalists)."""
    from collections import Counter

    stamp = tuple(_fantasy_history_stamp(fmt) for fmt in ("t20", "odi", "test"))
    if _TEAMS_CACHE["stamp"] == stamp and _TEAMS_CACHE["payload"] is not None:
        return _TEAMS_CACHE["payload"]

    names, venues = set(), set()
    venue_counts: Counter = Counter()
    for fmt in ("test", "odi", "t20"):
        try:
            fantasy = get_fantasy(fmt)
        except FileNotFoundError:
            continue
        for matches in fantasy.values():
            for stats in matches.values():
                if stats.get("team"):
                    suffix = " Women" if stats.get("gender") == "female" else ""
                    names.add(stats["team"] + suffix)
                venue = stats.get("venue")
                if venue:
                    venues.add(venue)
                    venue_counts[venue] += 1

    try:
        datewise = get_datewise_json()
        for leagues in datewise.values():
            if not isinstance(leagues, dict):
                continue
            for league, fixtures in leagues.items():
                if not isinstance(fixtures, dict):
                    continue
                is_women = "women" in str(league).lower()
                for info in fixtures.values():
                    if not isinstance(info, dict):
                        continue
                    for field, players in info.items():
                        if field == "Format" or str(field).endswith("_Second_Squad") or not isinstance(players, list):
                            continue
                        if len({str(p).strip() for p in players if str(p).strip()}) < 11:
                            continue
                        label = str(field).strip()
                        if label:
                            if is_women and "women" not in label.lower():
                                label = f"{label} Women"
                            names.add(label)
    except (OSError, ValueError, TypeError):
        pass

    if venue_counts and _vreg._REGISTRY is None:
        _vreg._REGISTRY = _vreg.VenueRegistry(venue_counts)

    # Case-fold dedupe for team labels; registry dedupe for venues
    by_cf = {}
    for n in names:
        by_cf.setdefault(n.casefold(), n)
    deduped_teams = sorted(by_cf.values())

    payload = {
        "teams": deduped_teams,
        "venues": _vreg.dedupe_venues(venues),
        "venue_stats": _vreg.registry_stats(),
    }
    _TEAMS_CACHE["stamp"] = stamp
    _TEAMS_CACHE["payload"] = payload
    return payload


@app.get("/venues")
def venues():
    raw = {m.get("venue") for m in get_matches_json() if m.get("venue")}
    return {"venues": _vreg.dedupe_venues(raw)}


# ─────────────────────────────────────────────────────────────────────────────
# POST endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/generate_best_team")
def generate_best_team_endpoint(request_data: GenerateRequest, user: Principal = Depends(require_user)):
    start = time.perf_counter()
    try:
        store = UserStore(user)
        store.consume_quota()
        result = generate_best_team(request_data.model_dump(exclude_none=True))
        result.setdefault("data_provenance", {}).update(
            artifact_release_id=STATE["release_id"],
            artifact_release_created_at=STATE.get("created_at"),
        )
        token = result["explain_token"]
        cached = _EXPLAIN_CACHE.get(token)
        if cached is None:
            raise HTTPException(503, "Explanation state unavailable; please retry")
        store.save_explanation(token, create_snapshot(cached), result)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Team generation failed; please retry")
    finally:
        print(f"[latency] generate_best_team {time.perf_counter() - start:.3f}s", flush=True)


@app.post("/explain_team")
def explain_team(request_data: ExplainRequest, user: Principal = Depends(require_user)):
    """
    SHAP feature drivers + natural-language analyst report (local Ollama).
    Body: {"explain_token": "<token from /generate_best_team response>"}
    """
    token = request_data.explain_token
    record = UserStore(user).get("explanations", token)
    if not record:
        raise HTTPException(
            status_code=404,
            detail="Explain token not found or expired. Re-run /generate_best_team.",
        )

    # Explanation rows are user-writable through the database API, so the
    # snapshot is untrusted input: bound the work it can request.
    cached = (record.get("payload") or {}).get("snapshot")
    if not _valid_snapshot(cached):
        raise HTTPException(status_code=400, detail="Explanation data is invalid. Generate the team again.")
    from intelligence.llm_analyst import generate_team_report

    if not _EXPLAIN_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Another report is being written. Please retry shortly.",
                            headers={"Retry-After": "10"})
    try:
        return generate_team_report(cached=cached, drivers_by_player=cached.get("drivers", {}))
    finally:
        _EXPLAIN_SLOTS.release()


# One report at a time: each one makes up to twelve local language-model calls.
_EXPLAIN_SLOTS = threading.BoundedSemaphore(1)
_MAX_SELECTED = 11
_MAX_PLAYERS = 100


def _valid_snapshot(cached) -> bool:
    if not isinstance(cached, dict):
        return False
    selected, players, drivers = cached.get("selected"), cached.get("players"), cached.get("drivers", {})
    return (isinstance(selected, list) and 0 < len(selected) <= _MAX_SELECTED
            and all(isinstance(key, str) for key in selected)
            and isinstance(players, dict) and len(players) <= _MAX_PLAYERS
            and all(key in players for key in selected)
            and isinstance(drivers, dict) and len(drivers) <= _MAX_PLAYERS)


@app.get("/auth/config")
def authentication_config():
    config = auth_config()
    return {"required": config["required"], "provider": "supabase",
            "phone_enabled": os.getenv("PHONE_AUTH_ENABLED", "false").lower() == "true"}


@app.get("/me")
def current_user(user: Principal = Depends(require_user)):
    return {"user_id": user.user_id, "is_admin": user.is_admin, "assurance_level": user.aal}


@app.get("/analyses")
def saved_analyses(user: Principal = Depends(require_user)):
    return {"analyses": UserStore(user).list_analyses()}


@app.post("/analyses", status_code=201)
def save_analysis(request_data: SaveAnalysisRequest, user: Principal = Depends(require_user)):
    return UserStore(user).save_analysis(request_data.explain_token, request_data.title)


@app.delete("/analyses/{analysis_id}")
def delete_analysis(analysis_id: str = APIPath(pattern=r"^[a-f0-9]{32}$"), user: Principal = Depends(require_user)):
    if not UserStore(user).delete_analysis(analysis_id):
        raise HTTPException(404, "Saved analysis not found")
    return {"deleted": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
