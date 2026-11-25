# NEW_X1

NEW_X1 analyses upcoming cricket fixtures and recommends a playing XI for T20, ODI and Test matches, with projected points, a captain and the reasons behind each pick. The [public website](https://new-x1.pages.dev/) is a static Next.js site on Cloudflare Pages. The FastAPI backend and saved ML models run on the operator's laptop and reach the website through an HTTPS tunnel whose address is published automatically.

## Project film

[![NEW_X1 launch film preview](frontend/public/launch-preview.gif)](https://new-x1.pages.dev/launch.mp4)

The full launch film plays in the preview above. Select it to watch with sound.

## Use the live site

Open [new-x1.pages.dev](https://new-x1.pages.dev/).

- **Fixtures** lists upcoming matches with their squad status. **Analyse** returns the best XI as a numbered scorecard, the projected team total, captain and vice-captain, conditions, and the bench.
- **Simulator** picks the best XI for any two teams, venue, format and date, with an adjustable risk appetite.
- **Account** signs in through Supabase and keeps saved analyses.

The website stays online at all times. Analysis works while the backend laptop is running; when it is off, the site says so and offers a [request to start it](mailto:riddhu.work@gmail.com?subject=NEW_X1%20backend%20request).

## Run the backend

From a provisioned Windows checkout with the Python environment, model artifacts and data available:

```powershell
.\run_all.bat
```

This starts one FastAPI process for all three saved models, opens a public tunnel and publishes its address, so the website connects without any manual step. To have it start whenever you sign in to Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
```

Then turn analysis on or off, or check it, from the repository folder:

```powershell
.\scriptsackend.ps1 start     # on (also automatic at sign-in)
.\scriptsackend.ps1 stop      # off; the website shows analysis as offline
.\scriptsackend.ps1 status    # task, models and published address
```

Address publishing needs a one-time Supabase setup; until then, paste the printed **PUBLIC API** address into the site's **Settings** page. For local checks without a tunnel, run `.\run_all.bat --local-only`. The [runbook](docs/RUNBOOK.md) covers setup, refresh and recovery. To run the backend on a cloud VM instead, see [deploy/oracle](deploy/oracle/README.md).

## Develop

Requirements: Python 3.10 or 3.11 and Node.js 22. Copy `.env.example` to an ignored `.env` and `frontend/.env.example` to `frontend/.env.local`; supply only the configuration needed for the features you use. Keep secrets out of Git and out of `NEXT_PUBLIC_*` variables.

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements.txt
Set-Location frontend
npm ci
npm run dev
```

The local web app is at `http://localhost:3000`. Run `python run_daily_sync.py` when the historical data pipeline needs a refresh; fixture and squad availability also depends on provider data. Training is explicit via `python model/train_model.py` and is not part of API startup.

## Verify

```powershell
.\env\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
Set-Location frontend
npm run lint
npm run build:static
```

The [Cloudflare Pages workflow](.github/workflows/deploy-cloudflare-pages.yml) builds and deploys frontend changes pushed to `main`. The Python verification workflow runs the test suite and static website checks. Runtime API details are in the [API reference](docs/API_REFERENCE.md); the [architecture](docs/ARCHITECTURE.md), [runbook](docs/RUNBOOK.md) and [Pitch Control report](docs/PITCH_CONTROL_REPORT_PLAN.md) describe the current system.

## Security

- Sign-in uses Supabase sessions verified with asymmetric keys; saved analyses are protected by row-level security.
- Analysis endpoints require sign-in and a daily quota; report generation is bounded and runs one at a time.
- The website sends sign-in tokens only to the published tunnel address, the configured build address or localhost.
- Model and data releases are verified by SHA-256 before loading.

## Repository map

- `frontend/`: website, account screens and simulator
- `model/`, `intelligence/`: API, prediction, optimization and venue analysis
- `data_processing/`, `data/future_matches/`: historical and upcoming data pipelines
- `pipeline/`: verified model and data releases, refresh worker and server entrypoint
- `supabase/migrations/`: account data, backend address and access policies
- `scripts/`: Windows auto-start for the laptop backend
- `deploy/oracle/`: Docker and HTTPS bundle for a cloud VM
- `tests/`: backend contracts and recovery tests
- `run_all.py`, `run_daily_sync.py`: one-step API launch and explicit data refresh

Historical venue evidence uses the last five and ten qualifying matches when possible; unsupported venues use a labelled curated or neutral fallback. The report is descriptive until its predictive effect is backtested. Saved model and validated data backups are retained for recovery.
