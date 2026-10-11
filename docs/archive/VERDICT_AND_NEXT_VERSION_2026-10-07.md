# NEW_X1 — updated verdict and remaining work

**Historical audit recorded 8 October 2026.** This document retains findings at that checkpoint. See the [current documentation index](../README.md) for the live deployment. The original report is preserved in [the 7 October audit](VERDICT_2026-10-07.md).

**Subsequent verified change:** commit `47041e4` fixes both deployment defects recorded below, implements tested release/recovery code, passes 111 local tests, and restores/boots actual artifacts with valid strict generation in all formats. Updated installed Python dependencies report no known vulnerabilities. This does not establish a live deployment, real Supabase activation, completed remote AWS recovery or a successful hosted CI run. The remaining scientific/data gates below stay open.

**Verdict: the core local application works, several release-blocking defects are fixed, and account integration plus the full pipeline runner are implemented in code. Public production readiness is incomplete. The current working directory contains an unfinished deployment draft with two reproduced defects.** Passing the existing suite does not validate that draft or establish a successful cloud deployment.

No Supabase or hosting account has been configured for this project. The user will create/configure those accounts manually. Live Google/OTP delivery, database policies, cloud scheduling, remote backups and production uptime have not been verified.

## What is implemented and pushed

At the audit start, local HEAD and remote `main` both pointed to `d68e4e291241150d4a8b661faeb31e2b58eff91b`.

| Step | Pushed commit | Implemented work | Status |
|---|---|---|---|
| Earlier M1–M5 | `974bb82` and earlier | Leakage guards, schema-v2 models, baseline evaluations, independent XI validation, ensemble explanations, local recovery and CI definition | Useful local implementation; outstanding acceptance criteria remain below |
| 1a: recovery | `50001a7` | Reject malformed fixture metadata; validate fitted/executable TriBE bundles; recover from incomplete/corrupt primaries using verified backups | Implemented and regression tested |
| 1b: correctness | `a2824fe` | Preserve prediction/retrospective modes; gender-aware exact resolution; backend-driven homepage fixtures; active bounded request schemas; truthful pitch, selection and uncertainty labels; deterministic explanation tests | Implemented and regression tested |
| 2: accounts | `7e6c461` | Supabase login UI, JWT verification, MFA gating, user-owned saved analyses, durable JSON explanations, database migration and generation quota | Code implemented; live provider/database activation pending |
| 3a: pipeline | `d68e4e2` | Configurable artifact roots; isolated deployed sync requirement; download, ingestion, features, full fixtures, imminent fallback and squads; timeouts, bounded retries, overlap lock, run records and squad budget | Runner implemented and fixed-data failure tests pass; no deployed scheduler yet |

**Uncommitted deployment work is not a completed step and has not been pushed.** Six new draft modules exist: `pipeline/object_store.py`, `releases.py`, `validate_release.py`, `worker.py`, `serving.py`, and `serve.py`. Draft edits also affect fixture/squad store defaults, `model/model_fastapi.py`, and `requirements.txt`. They aim to provide private S3 storage, checksum manifests, conditional promotion, isolated workers, whole-release recovery and background serving refresh. They need corrections and tests before a deployment commit.

Dockerfiles, Render configuration, a complete deployment guide and Linux/container verification have **not** been completed. No cloud deployment has been performed.

## Fresh audit checks

These checks were rerun after implementation was paused. Application code was not repaired during this audit.

| Check | Result | Practical limit |
|---|---|---|
| Python unittest discovery | **93 passed**, 4.427 seconds | Existing suite passes on this checkout; deployment drafts lack their required recovery tests |
| Frontend lint | **Passed** | Static checks |
| Frontend production build | **Passed**, Next.js 16.3.6 | Compilation/types/page generation, not a browser login journey |
| Production npm dependency audit | **0 vulnerabilities reported** | Current production npm graph, not a full security assessment |
| Full npm audit | **5 high findings** | Development ESLint/glob dependency chain remains open |
| Python `pip check` | **No broken requirements** | Existing Windows environment, not a clean Linux install or vulnerability audit |
| Actual T20 model | **Loaded**, CatBoost, 324 features, current source | Compatible artifact loads |
| Actual ODI/Test models | **Loaded**, TriBE, 324 features each, current source | Complete ensembles pass executable loader checks |
| Fixtures/squads | **29 future fixtures; 22 have usable squads** | Seven currently lack usable player pools; no feed warning at check time |
| Draft `/live` | **HTTP 200** | Process liveness only |
| Draft `/ready` with production-shaped configuration | **HTTP 500** | Reproduced code defect without a real Supabase request |
| Draft release validation on actual artifacts | **Failed** | Validator rejects supported cold-start missing values |
| Docker daemon | **Unavailable** | CLI exists, but Linux engine was not running; no container build verified |
| Hosted CI, live Supabase, remote storage and deployment | **Not verified** | Needs clean hosted execution and configured external services |

Fixtures were fetched at `2026-10-07T15:16:47.010446`; squads at `2026-10-07T17:28:41.573812`. Existing snapshots have legacy timestamps without timezone offsets; new pipeline refresh code writes UTC timestamps. Counts and freshness are time-dependent.

### Two open defects in the local deployment draft

1. **Readiness uses a nonexistent authentication field.** `ready()` accesses `auth_config()["configured"]`, but that contract returns `required`, `url`, and `key`. Required authentication with nonempty configuration raises `KeyError: 'configured'`, returning HTTP 500. Correct the contract and test absent, invalid and configured production settings before using readiness for hosting.
2. **Release validation disagrees with inference preprocessing.** The draft requires every feature cell to be finite. Chronological lag features legitimately have missing values at the beginning of a player's history, while inference fills missing values with zero. T20 feature columns contain **1,889,795 missing cells and zero infinite cells**. This is not evidence of corruption. Align validation with the supported missing-value contract while continuing to reject invalid schemas and unusable data; verify actual artifacts before promotion.

Neither defect was fixed during this pause. Do not use the draft serving entrypoint as a production release.

## Product functionality already available

The original requested frontend-to-API connection, Optimal XI/player cards, custom simulator, intelligence integration and explanation paths exist. The user frontend now uses **Next.js 16.3.6**, not the version stated in the original overview. A legacy internal Streamlit evaluation interface remains and was not re-audited here.

- T20, ODI and Test prediction use schema-v2 artifacts and chronological availability guards. **T20 uses CatBoost; ODI and Test use TriBE.** The claim that every format currently uses TriBE is inaccurate.
- The independent XI validator checks 11 unique eligible pool players, supported role bounds, team distribution and captain/vice-captain membership. Strict constraints are the default; relaxation requires an explicit request.
- Homepage fixtures come from the backend's actual squad validation. The UI no longer assumes access to another host's data files. Missing squads stay unavailable rather than fabricated.
- Weather/injury paths, curated pitch adjustments, SHAP drivers and deterministic explanation fallback exist. Their presence does not prove every adjustment improves prediction accuracy.
- Ensemble attribution uses meta-model weights. Selected-player drivers are captured during generation and stored as JSON, so explanations can survive a process restart rather than rely exclusively on an in-memory token.

### Authentication and accounts

The Account UI supports Google sign-in, email OTP, optional phone OTP, TOTP enrollment/verification, logout, verified Google linking, and saved-analysis viewing/deletion. Google Authenticator is an additional factor, separate from Google sign-in.

Backend checks include asymmetric JWT signatures, issuer, audience, expiry and identity. Trusted account metadata controls administrator status; editable user metadata cannot grant privileges. Administrators require AAL2, and enrolled MFA factors gate protected operations. Production/staging configuration fails closed.

The SQL migration defines user-owned history/explanation tables, RLS and an atomic **20 generation attempts per user per UTC day** quota. Queries additionally filter by owner. Explanation snapshots expire after one hour; saved analyses retain results. SQLite is explicit local development storage, not a production fallback when Supabase fails.

**At the time of this audit:** migration execution, RLS/quota behavior, Google callback, SMTP/SMS delivery, OTP abuse controls, linking/recovery and cross-user access against a real project were pending. See [account activation instructions](../AUTH_SETUP.md) for the current setup.

## Model-quality verdict

The following is the existing saved chronological evaluation evidence, previously rerun on 7 October. This paused audit reloaded models but **did not rerun the full evaluation or retrain them**.

| Format | Evaluated matches | Model MAE | Recent-form baseline MAE | Improvement | Interval coverage / target |
|---|---:|---:|---:|---:|---:|
| T20 | 1,358 | 23.76 | 27.36 | 13.2% | 73.1% / 80% |
| ODI | 200 | 30.81 | 34.63 | 11.0% | 71.7% / 80% |
| Test | 44 | 47.83 | 57.48 | 16.8% | 72.9% / 80% |

Separate training metric files report MAE **23.6088 / 30.6992 / 47.5440** with different test-row counts. Do not present these as the same measurement as the match-level evaluation above.

The models beat recent form on this evidence. They do not predict exact future points or guarantee the best realized XI. The optimum is relative to the chosen objective, predictions, candidate pool and constraints. Test-format evaluation has only 44 matches.

Uncertainty ranges are now labelled as uncalibrated historical spread, rather than an achieved 80% prediction interval. Calibration and untouched holdout checks remain required. Risk, captaincy, pitch and selection-probability claims need their own evaluation.

## Hardcoded data and backups

| Category | Current treatment | Remaining work |
|---|---|---|
| Scoring rules, roles, constraints, coordinates | Reference rules/configuration | Complete independent scoring examples and version stamps; review supported competition rules |
| Pitch profiles | Curated T20 priors labelled; unsupported measured averages omitted; ODI/Test and unknown venues neutral/unavailable | Derive format-specific measured statistics with sample sizes/cutoffs before adding measured claims |
| Injury, risk and captaincy weights | Heuristic adjustments | Calibrate and test benefit; distinguish unknown fitness from verified evidence |
| Playing probability | Unsupported 100% probability removed; selection marked unconfirmed | Confirmed-XI ingestion and probability calibration |
| Local recovery | Verified last-good model/data/feed files with source/fallback reporting | Same-machine copies do not cover disk/host loss; remote release/restore unfinished |
| Weather/news/LLM failure | Unknown/neutral adjustments or deterministic explanations | Hosted failure drills and real provider checks; no hosted Ollama configured |
| Authentication/storage failure | Fail protected operations rather than bypass identity/ownership | Provider recovery, delivery alternatives and database backup/restore |

A backup should supply previous verified evidence, a labelled lower-confidence path, or a controlled unavailable response. It cannot guarantee a prediction when no valid history or legal pool exists. No successful off-machine restoration has been demonstrated.

## What remains, in execution order

| Priority | Work left | Evidence needed to close it |
|---|---|---|
| P1 | Fix/test deployment draft | Correct both reproduced failures; validate real artifacts for all formats |
| P1 | Durable artifact release system | Checksum/schema rejection, complete-release consistency, conflicting publication protection, corrupt-current recovery, invalid-both refusal, rollback and private writer permissions |
| P1 | Deployment definitions | Backend container, frontend hosting configuration, scheduler definition, environment separation, current runbook and full manual guide; clean Linux install/build |
| P1 | Supabase/provider activation | Migration, signing keys, redirects, Google, SMTP and optional SMS; real ownership, MFA, quota and expired/reused OTP checks |
| P1 | Deployed scheduled pipeline | Actual full schedule; suitable provider budgets; failed-run alerts; old release survives failure; API observes verified new releases |
| P1 | Off-machine backups/recovery | Versioned remote model/data storage and database backup policy; measured restore and post-restore prediction smoke checks |
| P1 | Operational/public-beta checks | Browser login → generate → explain → save → reload/logout; latency/error/memory/concurrency measurements; capacity/rate limits, alerts and recovery/support |
| P1 | Scoring/full-data gates | At least 30 hand-verified innings across formats; scoring-version stamps; two unchanged full-dataset runs with hash equality; injected failure exits |
| P2 | Historical player identity collisions | Registry IDs where available and ingestion collision report; gender fix does not solve same-name players |
| P2 | Calibrate uncertainty/heuristics | Chronological validation and untouched holdout; coverage by format/experience; risk-weight sensitivity |
| P2 | CI/security/dependencies | Observe hosted CI; Linux/container checks; Python vulnerability audit; development findings assessment/fix; secret scanning and key rotation procedure |
| P2 | Account lifecycle/retention | Self-service deletion or verified support process; recovery; expired-snapshot/quota cleanup; retention/privacy policy |
| P2 | Remaining squad availability | Seven current fixtures lack usable squads; verify coverage, identities/roles and provisional versus confirmed selection |
| P3 | Future product improvements | Confirmed-XI/toss updates, player lock/exclude, alternatives, quality dashboard, model monitoring, PWA and opt-in reminders after release gates |

The 3a runner has timeouts, required-stage stopping, overlap protection and a default **three-request squad budget**. That controls requests but does not guarantee full squad coverage. The live full pipeline, full-dataset unchanged rerun and cloud scheduler have not been verified. Nightly retraining/model promotion is not completed; model changes must pass evaluation before promotion.

Older issue-register/runbook descriptions need reconciliation before deployment. A CI YAML file, migration or release module does not by itself close its operational gate. Python vulnerability auditing was not performed; `pip_audit` is not installed in the current environment.

## Manual activation plan for the user

Supabase is selected. The proposed beta layout remains Next.js hosting + dedicated FastAPI + scheduled worker + Supabase + private versioned object storage. Budgets and instance sizes are not selected or provisioned.

1. **Create Supabase.** Record the project URL/publishable key; keep credentials in environment settings. Apply the committed migration, configure asymmetric signing keys, and set exact site/redirect URLs. Never put service-role or provider secrets in frontend variables.
2. **Enable Google/email OTP.** Use the callback URL supplied by Supabase. Configure production SMTP and the `{{ .Token }}` template; test delivery and invalid/expired/reused codes. Follow [Google setup](https://supabase.com/docs/guides/auth/social-login/auth-google), [redirect configuration](https://supabase.com/docs/guides/auth/redirect-urls), [email OTP](https://supabase.com/docs/guides/auth/auth-email-passwordless), and [SMTP setup](https://supabase.com/docs/guides/auth/auth-smtp).
3. **Enable phone after delivery testing.** Configure SMS country support, costs/abuse limits and both phone flags. Enroll TOTP and verify it after a fresh login. Google/email remain alternatives without bypassing ownership verification.
4. **Create private storage/hosting accounts.** Enable versioning/retention; give API read access and worker controlled write access; establish database backups. Independent hosts cannot assume shared local files. [Render cron jobs](https://render.com/docs/cronjobs) cannot access persistent disks, which is why durable artifact exchange is required.
5. **Wait for the deployment code gate before activation.** Fix/test/push the draft and finish hosting definitions plus a tested initial artifact seed. The current draft is not a finished deployable package.
6. **Activate staging first.** Set backend auth/CORS/storage/provider values and frontend API/Supabase values; rebuild when public frontend variables change. Test all formats and the account/save journey, an actual scheduled run and a failed-refresh/restore drill.
7. **Open a bounded beta.** Configure domain/HTTPS, alerts, budgets, recovery/support and privacy/retention rules. Record measured limits and remaining forecast limitations. Public activation remains pending; zero issues cannot be guaranteed.

[AUTH_SETUP.md](../AUTH_SETUP.md) contains detailed account configuration. This paragraph records the state at the audit date; see the [current documentation index](../README.md) for deployment status.

## Resume point

Resume at **Step 3b**: correct the two draft defects and add release/recovery tests before committing that step. Then finish deployment definitions, operational verification and the manual guide. Keep the uncommitted draft for continuation; do not count it as pushed, verified or live.

**The enterprise-grade/live/full-pipeline acceptance goal is not complete.** Verified local work, pending provider activation, unfinished code and scientific validation gaps must remain separate in release claims.
