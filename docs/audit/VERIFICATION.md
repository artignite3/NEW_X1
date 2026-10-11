# Verification record

**Date:** 11 October 2026. Commands below ran from the `NEW_X1_cloudflare` source checkout unless a working directory is stated. The source checkout contains pre-existing uncommitted product/video work; this audit did not reset it. The complete local artifact checkout was used only as a Python runtime and read-only model/data root.

| Check / exact command | Result | Scope and limit |
|---|---|---|
| `env/Scripts/python.exe -m pip check` | PASS, exit 0 | Source venv metadata has no broken installed requirements; it is incomplete. |
| `env/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v` | FAIL, exit 1 | 39 discovered, 12 import errors from missing packages such as `jwt`, `fastapi`, `numpy`, `requests`; environment issue, not a code pass. |
| `env/Scripts/python.exe -m pip install -r requirements.txt --disable-pip-version-check` | INCOMPLETE, interrupted | The clean source venv began downloading the 124.9 MB pinned XGBoost wheel, then produced no further progress for several minutes; the attempt was stopped. The source venv still needs installation on a working package network. No requirements were changed. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe -m pip check` | PASS, exit 0 | Complete artifact venv dependency consistency. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v` | PASS, exit 0 | Baseline 137; final run 139 unit/integration-contract tests in 7.58 seconds after two new regressions. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe -m unittest tests.test_resilience_and_explanations.FeedRecoveryTests.test_future_fetch_timestamp_uses_verified_backup tests.test_resilience_and_explanations.FeedRecoveryTests.test_future_squad_timestamp_uses_verified_backup -v` | PASS, exit 0 | Future-dated fixture and squad feeds fall back to valid backups and publication is rejected. |
| `npm run lint` (`frontend`) | PASS, exit 0 | ESLint on current frontend. |
| `npm run build` (`frontend`) | PASS, exit 0 | Next.js 16.3.8 standalone production build and route generation. |
| `npm run build:static` (`frontend`) | PASS, exit 0 | Static export used by Cloudflare Pages. |
| `npm audit --omit=dev --json` (`frontend`) | PASS, exit 0 | No known production npm vulnerabilities in the current audit database. |
| `npm audit --json` (`frontend`) | FAIL, exit 1 | Five high development-tool findings through ESLint/glob/braces; production dependencies unaffected by this result. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe -m pip_audit -r requirements.txt --progress-spinner off` | PASS, exit 0 | No known advisories in pinned Python requirements at query time; pip-audit warned its local cache write failed. |
| TestClient `GET /health`, `/matches`, `/openapi.json` with explicit artifact data/model roots | PASS, HTTP 200 | All three saved models loaded; `/health` `degraded` because fixture feed is stale; 27 fixtures and 26 squad-ready sources; OpenAPI served. Test environment, not public deployment. |
| Tracked-source credential-pattern check (`git ls-files -z` plus Python regex for private-key blocks, Supabase secret keys, GitHub tokens and AWS access IDs) | PASS with caveat | Zero high-confidence matches. Ignored files and Git history were not examined. |

The new fixture and squad validators accept legacy timezone-naive timestamps as UTC but reject timestamps more than five minutes ahead. This avoids treating bad future metadata as a fresh feed while preserving existing snapshots. Saved metrics are T20 MAE 23.6088 (`n_test=29,880`), ODI MAE 30.6992 (`n_test=4,401`) and Test MAE 47.544 (`n_test=970`); these are artifact metadata, not a rerun of `model.evaluate` or a prospective accuracy claim.

## Final check results

| Check / exact command | Result | Limit |
|---|---|---|
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'` | PASS, exit 0: 139 tests | Fixed-data suite with complete artifact venv. |
| `npm run lint` and `npm run build:static` from `frontend` | PASS, exit 0 each | Static export generated all site routes; not a browser integration test. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe scripts/check_docs.py --include-archive` | PASS, exit 0: 52 Markdown files, zero missing local targets | File/image paths only; external URLs and semantic accuracy need separate review. |
| `git diff --check` | PASS, exit 0 | No tracked diff whitespace errors. |
| `git ls-remote --heads origin main pitch-control-report` | PASS, exit 0 | Both remote refs point to `a7a71b07dff32a689021f54647cecb1beb339b92`; this does not include current uncommitted changes or prove Cloudflare deployed that commit. |
| `curl.exe -L -I --max-time 15 https://new-x1.pages.dev/` | PASS, HTTP 200 | Public static site responded; no version fingerprint or full browser/auth/API check. |
| `docker info --format '{{.ServerVersion}}'` | BLOCKED, exit 1 | Docker CLI 29.8.0 exists, but the local Linux engine pipe is unavailable; container builds were not run. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe run_all.py --help` and `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe run_daily_sync.py --help` | PASS, exit 0 each | Documented launcher/data-sync entry points and flags parse; no data refresh or tunnel was started. |
| TestClient `POST /generate_best_team` with `match_id=169931`, `use_ml=true`, `use_intelligence=false`, explicit artifact roots and local test principal | PASS, HTTP 200 | ODI TriBE generated 11 players, strict mode, `validation.valid=true` in ~7.5–8.6 seconds. A configured Supabase environment correctly returned 401; the offline smoke explicitly cleared auth values after loading `.env`. Production authentication was not bypassed. |
| TestClient `POST /explain_team` with the just-generated token and same local test principal | PASS, HTTP 200 | Returned `attribution`, `context`, `generated_with`, `players`, `team_report`; public account/tunnel integration still untested. |
| TestClient `GET /matches` source breakdown | PASS, HTTP 200 | 27 fixtures: 5 `provider`, 14 `series_squad`, 7 `last_match`, 1 `pending`. Last-match pools are provisional. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe scripts/smoke_local.py --artifacts-root 'D:\Personal Coding\Data Science and ML\NEW_X1' --match-id 169931` | PASS, exit 0 | Reproducible combined health/fixture/generation/explanation check: three models loaded, 27 fixtures, 26 usable squad pools, 11-player strict validated XI, explanation returned. Health remains degraded for stale fixture metadata. The first helper run failed on its own import path; `sys.path` was corrected and the same command passed. |
| `D:\Personal Coding\Data Science and ML\NEW_X1\env\Scripts\python.exe -m uvicorn model.model_fastapi:app --host 127.0.0.1 --port 18080`; `Invoke-RestMethod http://127.0.0.1:18080/health`; `Invoke-RestMethod http://127.0.0.1:18080/live` | PASS | Real Uvicorn process started; both routes returned HTTP 200. `/health` was `degraded` only because the fixture feed was stale; all three model flags were true. Process was stopped and no listener remained on port 18080. |
| High-confidence credential-pattern scan of 176 source/documentation text files, excluding ignored env/output/dependency/media directories | PASS with caveat | No private-key block, Supabase secret, GitHub token or AWS access-key ID pattern found; heuristic and not a Git-history scan. |

Skipped/blocked: no live Supabase two-user/RLS or OAuth/SMS/TOTP test; no public Cloudflare tunnel/browser session; no verified GitHub Actions run or new deployment; no fresh provider pull; no container build because the daemon is unavailable; no new training or scientific holdout evaluation. These are not reported as passed.
