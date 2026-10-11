# NEW_X1 API and recovery contract

Run `env/Scripts/python.exe -m uvicorn model.model_fastapi:app --host 127.0.0.1 --port 8000` from the repository root after restoring dependencies, data and models. Interactive request schemas are at `/docs`. The public Pages site needs the API behind a working HTTPS tunnel. Configured staging/production account and generation routes require `Authorization: Bearer <Supabase access token>`; local `APP_ENV=test` or `development` without Supabase values can use the anonymous test principal.

`GET /` returns the API name/version and docs path. `GET /live` returns process liveness (`{"status":"alive"}`) without asserting model or data readiness. `GET /ready` is for the optional verified release-worker deployment and returns 503 unless authentication settings and a recent release are valid; a laptop launch may be usable while `/ready` is 503.

## `GET /health`

Returns `status` (`ok` or `degraded`), model availability by format, Ollama reachability, and `sources` for models, features, and fantasy history. Model sources are `current`, `last_good`, or `unavailable`; large data sources remain `unchecked` until first analysis, then show their active source. `data_checked_on_request` documents this lazy check. `fixtures` and `squads` include `fetched_at`, `fallback_used`, and `warning`. A known fallback, stale fixture feed (over 24 hours), or unavailable model makes status `degraded`. Ollama being offline does not prevent generation.

## `GET /matches`, `GET /match_squads?match_id=...`

`/matches` serves only future, unended, schema-validated fixtures, with feed provenance and warnings. A verified last-good snapshot is used if the primary feed is damaged. If neither copy is valid, `matches` is empty and `warning` explains why. Each match has `has_squad` and `squad_source`: `provider`, `series_squad`, `last_match`, or `pending`. The latter two usable sources are provisional and may include source match IDs/dates. `/match_squads` returns normalized player names, role, team, injury status and name-resolution preview for a known fixture, or 404 if the fixture/pool is unavailable. Neither endpoint invents fixtures or players. `GET /teams` returns known teams, canonical venues and registry statistics from saved histories; `GET /venues` lists normalized venues from future fixtures.

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

The request is Pydantic-validated (422 for malformed IDs, dates, unsupported formats, extra fields or out-of-range risk values). Configured authentication can return 401/403/503 before generation. A per-user daily quota can return 429. The response carries an `explain_token` valid for one hour.

## `POST /explain_team`

Pass `{"explain_token":"<token from generation>"}` within one hour under the same account. The report returns selected-player drivers and narrative plus `attribution.method` and `attribution.available`. ODI/Test drivers combine full CatBoost, XGBoost, and LightGBM SHAP vectors using the fitted linear meta-model weights. If a required explainer fails, no partial ensemble drivers are presented. Ollama is optional; heuristic narration remains available and labels missing attribution explicitly.

The token must be a 32-character lowercase hex value; malformed input returns 422, unknown/expired token returns 404. Explanations are persisted in the selected user store, so an API-process restart can retain them while storage remains available.

## Account routes

`GET /auth/config` reports whether Supabase authentication is required and whether phone login is enabled. `GET /me` returns the verified user ID, admin flag and assurance level. `GET /analyses` lists up to 100 of the user's saved analyses. `POST /analyses` accepts `{"explain_token":"<32 hex>","title":"<1–120 chars>"}` and returns a saved record (201). `DELETE /analyses/{analysis_id}` deletes only that user's saved record and returns `{"deleted":true}` or 404. Supabase RLS and an explicit owner filter protect remote data; local SQLite is only for explicit development/test operation. These routes need live two-user/RLS verification before production claims.

## Recovery operation

Run `env/Scripts/python.exe data_processing/seed_backups.py` once after a healthy install. It validates current fixtures, squads, fantasy histories, feature tables, and schema-v2 models before creating missing local `last_good` copies. Future refreshes use atomic promotion and keep a prior copy. Backups are local and ignored by Git; copy them separately for off-machine disaster recovery. If both current and backup are invalid or expired, the API reports degraded/unavailable instead of fabricating a result.

Verify with `env/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v`, `npm run lint`, and `npm run build` from `frontend`. The resilience tests use fixed inputs and deliberately corrupt primary artifacts to verify fallback. Evaluate saved models against the recent-form baseline with `env/Scripts/python.exe -m model.evaluate t20 odi test`.
