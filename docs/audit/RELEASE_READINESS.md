# Release-readiness decision

**Current verdict: NOT READY for a fully available public backend/ML release.** The local core checks are encouraging: the complete Python environment passed its suite; all three models loaded through the API; frontend lint and static build passed; Python and production npm dependency audits reported no known vulnerabilities. The committed Pitch Control HEAD is on remote `main`, and the public static site responds with HTTP 200. The fixture feed is already stale, the full npm audit flags development dependencies, and this audit has not verified live Supabase authorization/RLS, a public tunnel, or a Cloudflare deployment of the current uncommitted worktree changes. A successful local build cannot close those gates.

| Dimension | Evidence / remaining gate |
|---|---|
| Functional correctness | Fixed-data suite and reproducible local ODI generation/explanation smoke pass; live browser/provider paths remain untested. |
| Tests/build | Final 139 Python tests and frontend lint/static build passed; source venv is incomplete. |
| Runtime/data | API responds locally with all three models; stale fixture warning means provider refresh is needed. |
| Security/dependencies | Auth design is fail-closed in configured environments; no live RLS test. Production npm/Python advisory checks pass; five development npm findings remain. |
| Reproducibility/science | Cutoff/schema tests exist; saved evaluation is not proof of future performance. Pitch-history multipliers stay neutral pending backtest. |
| Deployment | Remote `main` contains committed Pitch Control code and the public site returns HTTP 200, but no new deployment or live browser/API check of worktree changes was performed here. Laptop/tunnel is operator-dependent. |
| Documentation | Folder guides, root navigation and a local-link checker were added; all 52 current/archive Markdown files have existing local targets. |

To change this verdict, restore a fully provisioned source environment, refresh fixtures/squads, perform a representative generation and explanation from the live website through the public tunnel, verify Supabase sign-in and cross-user RLS/quota in the selected project, inspect a successful Cloudflare Pages deployment of the intended commit, and decide whether a temporary laptop backend meets the release availability requirement. See the [issue register](ISSUES.md) and [verification log](VERIFICATION.md). No commit, push, publish, deploy or release was performed by this audit.
