"""Exercise saved models through the API in an isolated local test process.

This sets APP_ENV=test and clears Supabase settings in this process only. It is
not a live authentication, tunnel, or production readiness test.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--match-id", help="prefer a specific future fixture")
    args = parser.parse_args()
    root = args.artifacts_root.expanduser().resolve()
    if not (root / "data" / "processed").is_dir() or not (root / "model_artifacts").is_dir():
        parser.error("artifact root must contain data/processed and model_artifacts")

    os.environ.update(APP_ENV="test", SUPABASE_URL="", SUPABASE_PUBLISHABLE_KEY="",
                      NEW_X1_DATA_ROOT=str(root / "data"), NEW_X1_MODEL_ROOT=str(root / "model_artifacts"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fastapi.testclient import TestClient
    from model.model_fastapi import app

    client = TestClient(app)
    health = client.get("/health")
    health.raise_for_status()
    models = health.json()["models"]
    if not all(models.get(fmt) for fmt in ("t20", "odi", "test")):
        raise RuntimeError(f"Saved models unavailable: {models}")
    feed = client.get("/matches")
    feed.raise_for_status()
    matches = feed.json()["matches"]
    ready = [m for m in matches if m.get("has_squad")]
    selected = next((m for m in ready if str(m["match_id"]) == args.match_id), None) if args.match_id else None
    if args.match_id and selected is None:
        raise RuntimeError(f"Fixture {args.match_id} is not future-dated with a usable squad pool")
    selected = selected or next((m for m in ready if m.get("squad_source") == "provider"), None)
    if selected is None:
        raise RuntimeError("No future fixture with a usable squad pool")
    generated = client.post("/generate_best_team", json={"match_id": str(selected["match_id"]),
                                                      "use_ml": True, "use_intelligence": False})
    generated.raise_for_status()
    result = generated.json()
    if len(result["best_team"]) != 11 or not result["validation"]["valid"]:
        raise RuntimeError("Generated team failed the independent validator")
    explanation = client.post("/explain_team", json={"explain_token": result["explain_token"]})
    explanation.raise_for_status()
    summary = {"health": health.json()["status"], "models": models,
               "fixture_count": len(matches), "ready_count": len(ready),
               "fixture_warning": feed.json().get("warning"),
               "match_id": str(selected["match_id"]), "source": selected.get("squad_source"),
               "team_size": len(result["best_team"]),
               "constraint_mode": result["summary"]["constraint_mode"],
               "validated": result["validation"]["valid"],
               "explanation_fields": sorted(explanation.json())}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
