# NEW_X1 — Issue Register

Severity: **P1** blocks a milestone gate · **P2** wrong/missing behavior without a
workaround · **P3** quality/hygiene. Each issue carries acceptance criteria (AC).

| ID | Sev | Area | Issue | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| #1 | P1 | ML | **Test model is pre-v2** and rejected by the guard; Test analyses run in recent-form mode | #3, #4 | `tribe_test.pkl` passes `validate_model_metadata`; Test-format eval beats recent-form baseline on chronological holdout |
| #2 | P1 | ML | **No model is validated.** v2 T20/ODI artifacts load and serve, but there is no published chronological evaluation (MAE, selection regret, interval coverage) proving they beat baselines | #3, #4 | `outputs/eval_<fmt>_<window>.csv` per format, produced by a fixed-seed chronological eval script, committed with the model metadata it used |
| #3 | P1 | Data | **Scoring spec is not independently verified.** Fantasy-points calculation (boundaries, wides/no-balls attribution, run-outs, fielding shares, maidens, super overs) has no hand-checked golden examples | #5 | ≥30 hand-verified innings across T20/ODI/Test agree exactly with `calculate_*` outputs; scoring version stamped into features and models |
| #4 | P1 | Data | **Feature leakage audit incomplete.** v2 removed `career_*` and added `available_date`, but venue/opponent rolling features and same-day/overlapping-Test leakage need systematic proof | #3 | Perturbation test: editing a match's outcome changes no earlier feature row (scripted, in CI) |
| #5 | P1 | Data | **Idempotent ingestion not yet proven twice-in-a-row** on the full dataset (manifests exist; second-run hash equality untested) | — | Second unchanged sync produces byte-identical `player_fantasy_points_*.json` + features; failure injection surfaces as non-zero exit |
| #6 | P2 | Data | Name-collision artifacts in fantasy data (e.g. T20 "Rashid Khan" merges unrelated players; Afghanistan missing from ODI set) | #3 | Player identity keyed by registry ID where available; collision report generated at ingestion |
| #7 | P2 | Product | Squad availability is fetched manually; WBBL (7 fixtures) pending publisher. No scheduled auto-refresh with failure reporting | #11 | Scheduled sync updates fixtures+squads; failures visible in UI freshness indicator |
| #8 | P2 | Solver | Solver silently relaxes constraints on infeasibility (role→team→greedy ladder). Plan requires explicit user-selected relaxation | — | Solver reports the constraint set used; strict mode returns infeasibility with reasons; relaxation only via request flag |
| #9 | P2 | Intelligence | Weather uses current-conditions endpoint for future dates; forecast-for-date provenance unverified | — | Date-matched forecast or explicit "forecast unavailable"; source + timestamp in response |
| #10 | P2 | ML | Risk-aversion λ (Σμ − λσ²) uncalibrated; default 0.05 chosen by inheritance, not evidence | #2 | λ chosen on validation data; sensitivity documented |
| #11 | P2 | Ops | No CI, no pinned dependency lock, no startup/shutdown checks | #3 | CI runs tests + build on push; `requirements.txt` pinned versions verified by clean install |
| #12 | P3 | API | Explain cache is in-process only; multi-worker deployments lose tokens | — | Token cache persisted or explain recomputes deterministically |
| #13 | P3 | Data | `player_fantasy_points` JSONs are 200-400 MB and re-parsed per process; consider parquet + column access | #4 | Warm request latency ≤ current; memory bounded |
| #14 | P3 | Ops | `.env` holds a live API key; repo has no secret-scanning pre-commit | #11 | Pre-commit secret scan; key rotation documented |

## Explicitly out of scope until gates pass
Model complexity increases (TriBE for T20), UI expansion, multi-tenant auth (#11 covers auth before any shared deployment).
