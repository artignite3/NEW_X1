"""One serving snapshot per request; refresh verifies outside the shared lock."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import re
import shutil
from fastapi import HTTPException, Request

SNAPSHOT_LOCK = threading.Lock()
STATE = {"release_id": None, "fallback_used": False, "refresh_error": None, "pipeline": None}
DATA_ROUTES = {"/health", "/ready", "/matches", "/match_squads", "/teams", "/venues", "/generate_best_team"}


def runtime_guard(request: Request):
    if request.url.path not in DATA_ROUTES:
        yield
        return
    # Single-analysis beta capacity also protects format caches from concurrent eviction.
    timeout = 1 if request.url.path == "/generate_best_team" else 5
    if not SNAPSHOT_LOCK.acquire(timeout=timeout):
        raise HTTPException(status_code=503, detail="Analysis service is busy. Please retry shortly.", headers={"Retry-After": "3"})
    try: yield
    finally: SNAPSHOT_LOCK.release()


def apply_release(root, manifest, recovery):
    """Caller holds SNAPSHOT_LOCK; old requests finish before cache paths change."""
    root = Path(root).resolve()
    os.environ["NEW_X1_DATA_ROOT"] = str(root / "data")
    os.environ["NEW_X1_MODEL_ROOT"] = str(root / "model_artifacts")
    from model import predict_model as prediction, team_generator as teams
    from data.future_matches import fixture_store, squad_store
    from intelligence import venue_registry
    prediction.DATA_PROCESSED = root / "data/processed"
    prediction.MODEL_ARTIFACTS = root / "model_artifacts"
    for name in ("_MODEL_CACHE", "_DF_CACHE", "_MODEL_STAMPS", "_DF_STAMPS", "_MODEL_SOURCES", "_DF_SOURCES"):
        getattr(prediction, name).clear()
    teams.DATA_PROCESSED = root / "data/processed"
    teams.FUTURE_MATCHES = root / "data/future_matches"
    for name in ("_FANTASY_CACHE", "_DATA_STAMPS", "_FANTASY_SOURCES", "_RESOLVER_CACHE", "_PRIOR_CACHE", "_EXPLAIN_CACHE"):
        getattr(teams, name).clear()
    for name in ("_SQUADS_JSON", "_MATCHES_JSON", "_DATEWISE_JSON", "_DATEWISE_STAMP", "_DATEWISE_INDEX"):
        setattr(teams, name, None)
    teams._DATEWISE_SOURCE = "unavailable"
    venue_registry._REGISTRY = None
    try:
        from model import model_fastapi
        model_fastapi._TEAMS_CACHE.update(stamp=None, payload=None)
    except Exception:
        pass
    fixture_store.HERE = root / "data/future_matches"
    fixture_store.PRIMARY = fixture_store.HERE / "upcoming_matches.json"
    fixture_store.BACKUP = fixture_store.HERE / "upcoming_matches.last_good.json"
    squad_store.PRIMARY = fixture_store.HERE / "upcoming_squads.json"
    squad_store.BACKUP = fixture_store.HERE / "upcoming_squads.last_good.json"
    STATE.update(release_id=manifest["release_id"], created_at=manifest["created_at"],
        validation=manifest.get("validation"), fallback_used=recovery["fallback_used"], refresh_error=None,
        root=str(root), file_names=list(manifest["files"]))
    STATE["file_stamps"] = file_stamps()


def file_stamps():
    root = Path(STATE["root"])
    result = []
    for name in STATE["file_names"]:
        try:
            stat = (root / name).stat()
            result.append((stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        except OSError: result.append(None)
    return result


def prune_cache(cache, pointer, active_id):
    """Keep current/previous and active releases; never traverse arbitrary paths."""
    root = Path(cache).resolve()
    keep = {active_id} | {Path(key).stem for key in pointer.values() if isinstance(key, str)}
    for path in root.iterdir():
        if (re.fullmatch(r"[a-f0-9]{32}", path.name) and path.name not in keep
            and path.is_dir() and not path.is_symlink() and path.resolve().is_relative_to(root)):
            shutil.rmtree(path)


def refresh_once(store, cache):
    from pipeline.releases import read_pointer, restore_release
    try:
        raw, _ = store.read("latest_run.json")
        pipeline = json.loads(raw) if raw else None
        pointer, _ = read_pointer(store)
        key = pointer.get("current")
        if (key == "releases/" + str(STATE["release_id"]) + ".json" and not STATE["fallback_used"]
            and STATE.get("root") and STATE.get("file_stamps") == file_stamps()):
            with SNAPSHOT_LOCK:
                STATE.update(pipeline=pipeline, refresh_error=None)
            return
        root, manifest, recovery = restore_release(store, cache)
        with SNAPSHOT_LOCK:
            if STATE["release_id"] != manifest["release_id"]: apply_release(root, manifest, recovery)
            else: STATE.update(fallback_used=recovery["fallback_used"], refresh_error=None)
            STATE["pipeline"] = pipeline
            prune_cache(cache, pointer, STATE["release_id"])
    except Exception as error:
        with SNAPSHOT_LOCK: STATE["refresh_error"] = type(error).__name__


def public_status():
    job = STATE.get("pipeline") or {}
    return {"release_id": STATE["release_id"], "created_at": STATE.get("created_at"),
        "fallback_used": STATE["fallback_used"], "refresh_error": STATE["refresh_error"],
        "last_pipeline_status": job.get("status"), "last_pipeline_finished_at": job.get("finished_at"),
        "history_latest_match": {fmt: (STATE.get("validation") or {}).get(fmt, {}).get("latest_match")
                                 for fmt in ("t20", "odi", "test")}}


def release_is_fresh(max_hours=72):
    if not STATE.get("created_at"): return False
    return (datetime.now(timezone.utc) - datetime.fromisoformat(STATE["created_at"])).total_seconds() <= max_hours * 3600
