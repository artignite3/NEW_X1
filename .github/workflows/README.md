# CI and deployment workflows

[`ci.yml`](ci.yml) installs Python dependencies, runs `pip check` and the `unittest` suite on Windows/Linux, runs frontend lint/build, builds API/web containers, and audits production npm/Python dependencies. [`deploy-cloudflare-pages.yml`](deploy-cloudflare-pages.yml) builds the static frontend and uploads `frontend/out` to the existing `new-x1` Pages project on relevant `main` pushes or manual dispatch.

The deployment job needs scoped `CLOUDFLARE_ACCOUNT_ID`/`CLOUDFLARE_API_TOKEN` secrets and public Supabase repository variables. It deploys only the website, not the laptop API or data sync. Verify a specific workflow run and the live URL before claiming deployment succeeded. Reproduce local checks via the [runbook](../../docs/RUNBOOK.md).
