# NEW_X1 API and recovery contract

Run `env/Scripts/python.exe -m uvicorn model.model_fastapi:app --host 127.0.0.1 --port 8000` from the repository root. Interactive request schemas are at `/docs`.

## `GET /health`

Returns `status` (`ok` or `degraded`), model availability by format, Ollama reachability, and `sources` for models, features, and fantasy history. Model sources are `current`, `last_good`, or `unavailable`; large data sources remain `unchecked` until first analysis, then show their active source. `data_checked_on_request` documents this lazy check. `fixtures` and `squads` include `fetched_at`, `fallback_used`, and `warning`. A known fallback, stale fixture feed (over 24 hours), or unavailable model makes status `degraded`. Ollama being offline does not prevent generation.

## `GET /matches`, `GET /match_squads?match_id=...`

`/matches` serves only future, unended, schema-validated fixtures, with feed provenance and warnings. A verified last-good snapshot is used if the primary feed is damaged. If neither copy is valid, `matches` is empty and `warning` explains why. `has_squad` is derived from the verified squad feed. `/match_squads` returns the normalized players and roles for a known fixture, or a 404 if the fixture or squad is unavailable. Neither endpoint invents fixtures or players.

## `POST /generate_best_team`

Fixture request:

```json
{"match_id":"151576","use_ml":true,"use_intelligence":true}
```

Custom simulator request:

```json
{"team1":"India","team2":"Australia","format":"t20","date":"2026-10-12","venue":"Neutral Venue","risk_aversion":0.05}
```

Optional flags are `scan_news`, `mode` (`prediction` or `retrospective`), and `allow_relaxation`. Prediction dates must be in the future. Retrospective dates must be before today and after the training cutoff. Default selection is `strict`. When `allow_relaxation` is explicitly true, the solver may report `relaxed_team` or `relaxed_roles`; the response always includes `summary.constraint_mode`, independent `validation`, and `data_provenance` showing active sources and warnings. Hard constraints (11 unique, available, pool-listed players and captain/vice-captain in the XI) remain mandatory. Infeasible requests return 400, unavailable required history returns 503, and unexpected errors return 500. If both model copies are unavailable, generation can use recent-form statistics and reports that fallback. `use_ml=false` explicitly selects that statistical engine.

## `POST /explain_team`

Pass `{"explain_token":"<token from generation>"}` within one hour in the same API process. The report returns selected-player drivers and narrative plus `attribution.method` and `attribution.available`. ODI/Test drivers combine full CatBoost, XGBoost, and LightGBM SHAP vectors using the fitted linear meta-model weights. If a required explainer fails, no partial ensemble drivers are presented. Ollama is optional; heuristic narration remains available and labels missing attribution explicitly.

## Recovery operation

Run `env/Scripts/python.exe data_processing/seed_backups.py` once after a healthy install. It validates current fixtures, squads, fantasy histories, feature tables, and schema-v2 models before creating missing local `last_good` copies. Future refreshes use atomic promotion and keep a prior copy. Backups are local and ignored by Git; copy them separately for off-machine disaster recovery. If both current and backup are invalid or expired, the API reports degraded/unavailable instead of fabricating a result.

Verify with `env/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v`, `npm run lint`, and `npm run build` from `frontend`. The resilience tests use fixed inputs and deliberately corrupt primary artifacts to verify fallback. Evaluate saved models against the recent-form baseline with `env/Scripts/python.exe -m model.evaluate t20 odi test`.
