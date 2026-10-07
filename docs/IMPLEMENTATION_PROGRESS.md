# NEW_X1 implementation progress

Started 8 October 2026. Each independently verified step is committed and pushed to `main` before the next step begins. **Implementation paused at the user's request on 8 October.** The [updated verdict](VERDICT_AND_NEXT_VERSION_2026-10-07.md) records the current audit; the original report is retained under `docs/archive`.

| Step | Scope | Status |
|---|---|---|
| 1a | Recover from malformed fixture metadata and incomplete/unfitted model bundles | Complete: 68 local tests passed; all three real models load; 21 recovery/explanation tests passed |
| 1b | Correct request modes, gender resolution, fixture API access and misleading intelligence labels; reconcile tests | Complete: 73 self-contained tests passed; frontend lint/build passed; all three real formats return prediction mode and valid strict teams |
| 2 | Supabase login, access checks, saved analyses and shared explanations | Code verified: 85 tests, frontend lint/build and zero production npm audit findings; live Supabase/RLS/Google/OTP activation pending project configuration |
| 3a | Isolated full scheduled pipeline, bounded stages and provider request budget | Code verified: 93 tests; ingestion failure stops publication, optional provider failure is reported, previous squads retained |
| 3b | Reproducible deployment and durable artifact releases | Paused: uncommitted draft, not pushed; readiness returns HTTP 500 and actual-artifact validation rejects supported cold-start missing values |
| 4 | Failure/restore/operational verification | Pending |
| 5 | Public beta on configured accounts/domain | Pending external account configuration |
| 6 | Product expansion after release gates | Pending |

Production OTP delivery and a live deployment require configured provider accounts. Code, tests and deployment definitions can be completed before those integrations are activated.

Commits pushed before the next step: `50001a7` (1a), `a2824fe` (1b), `7e6c461` (2), `d68e4e2` (3a). Step 2 introduces JSON explanation persistence, owner-filtered account APIs, the Supabase SQL migration and Account UI. The deployment backend defaults to required authentication; the existing local `.env` explicitly selects development mode. Next.js was patched to 16.3.6. Five development-only ESLint glob-chain advisories remain without a compatible published fix; runtime npm audit is clean. Full uncertainty calibration, registry identities, the 30-innings scoring target and full-dataset idempotency remain open beyond the immediate product fixes.

Paused audit checks: 93 Python tests passed; frontend lint/build passed; production npm audit reported zero vulnerabilities; all three real models loaded; `pip check` passed. These results do not validate the unfinished deployment draft. Docker's Linux engine was unavailable; hosted CI, real Supabase policies/providers, remote release restoration and cloud scheduling remain unverified. No application-code corrections were made during the pause.
