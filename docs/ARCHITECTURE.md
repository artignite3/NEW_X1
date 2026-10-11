# NEW_X1 architecture

The public [website](https://new-x1.pages.dev/) is a static Next.js export. GitHub Actions builds `frontend/out` from `main` and uploads it to the existing Cloudflare Pages project. The site remains available when the analysis service is down.

| Component | Current role | Source |
|---|---|---|
| Next.js frontend | Fixtures, simulator, account and settings pages; shows API availability and offline contact notice | `frontend/src/` |
| Supabase | Browser sign-in and user-owned account data; the API verifies sessions on protected routes | `frontend/src/lib/auth.ts`, `model/auth.py`, `supabase/migrations/` |
| FastAPI backend | Match, squad and venue data; model inference, team generation and explanations | `model/model_fastapi.py` |
| Laptop launcher | Starts one inference API, checks all three models, and maintains a temporary tunnel for Pages | `run_all.py`, `run_all.bat` |
| Cricket data pipeline | Cricsheet ingestion, incremental features, fixtures and squads | `run_daily_sync.py`, `data_processing/`, `data/future_matches/` |
| Venue intelligence | Last-five/last-ten historical reports with curated or neutral fallback | `intelligence/venue_history.py`, `intelligence/venue_registry.py` |
| Local recovery | Validated last-good feeds, model and data copies; reports degraded state instead of inventing data | `data_processing/safe_publish.py`, `data_processing/seed_backups.py` |

The full Python API and ML models currently run on a laptop. A temporary HTTPS tunnel makes the API reachable while that laptop and tunnel are running; visitors can save the current tunnel address on the website's Settings page. The API's `/health` endpoint reports model and feed state, and the frontend checks it with a timeout. Cloudflare Pages does **not** host the Python models or run the daily pipeline.

The repository also retains a Render/AWS design in [the archive](archive/RENDER_DEPLOYMENT_GUIDE_2026-10-08.md). It is a future hosting option, not the active public deployment. Model archives, tracked evaluation evidence and generated-data manifests are retained for rollback and reproducibility. See the [runbook](RUNBOOK.md) for operations and [Cloudflare guide](CLOUDFLARE_DEMO.md) for deployment.
