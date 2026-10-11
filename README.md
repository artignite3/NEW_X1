# NEW_X1

NEW_X1 analyzes upcoming cricket fixtures and recommends a playing XI for T20, ODI and Test matches. The [public website](https://new-x1.pages.dev/) is a static Next.js site on Cloudflare Pages. The FastAPI backend and saved ML models run on the operator's laptop and are available to the website only while its HTTPS tunnel is running.

## Project film

[![NEW_X1 launch film preview](frontend/public/launch-preview.gif)](https://new-x1.pages.dev/launch.mp4)

The full launch film plays in the preview above. Select it to watch with sound.

## Use the live site

Open [new-x1.pages.dev](https://new-x1.pages.dev/). Fixtures show whether provider, series or dated last-match squads are available; an incomplete two-team pool remains pending. The Custom Simulator accepts a manually selected match. If analysis is offline, request that the backend be started by [email](mailto:riddhu.work@gmail.com?subject=NEW_X1%20backend%20request) or [message](https://wa.me/918982094147).

The site uses Supabase for account access. Match analysis is supplied by the separate laptop API. The website remains online when that API is offline.

## Run the backend

From a provisioned Windows checkout with the Python environment, model artifacts and data available, run:

```powershell
.\run_all.bat
```

This starts one FastAPI process for all three saved models and attempts a temporary public tunnel. When it prints **PUBLIC API**, enter that HTTPS origin in the site's **Settings** page and select **Save and test connection**. Keep the terminal open. The address can change after a restart. For local verification without a tunnel, run `.\run_all.bat --local-only`. See the [runbook](docs/RUNBOOK.md) for setup, refresh and recovery.

## Develop

Requirements: Python 3.10 or 3.11 and Node.js 22. Copy `.env.example` to an ignored `.env` and `frontend/.env.example` to `frontend/.env.local`; supply only the configuration needed for the features you use. Keep secrets out of Git and out of `NEXT_PUBLIC_*` variables.

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements.txt
Set-Location frontend
npm ci
npm run dev
```

The local web app is at `http://localhost:3000`. Run `python run_daily_sync.py` when the historical data pipeline needs a refresh; fixture/squad availability also depends on provider data. Training is explicit via `python model/train_model.py` and is not part of API startup.

## Verify

```powershell
.\env\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
Set-Location frontend
npm run lint
npm run build:static
```

The active [Cloudflare Pages workflow](.github/workflows/deploy-cloudflare-pages.yml) builds and deploys frontend changes pushed to `main`. The Python verification workflow runs the test suite and static website checks. Runtime API details are in the [API reference](docs/API_REFERENCE.md); the [architecture](docs/ARCHITECTURE.md), [runbook](docs/RUNBOOK.md), and [Pitch Control report](docs/PITCH_CONTROL_REPORT_PLAN.md) describe the current system.

## Repository map

- `frontend/`: website, account screens and simulator
- `model/`, `intelligence/`: API, prediction, optimization and venue analysis
- `data_processing/`, `data/future_matches/`: historical and upcoming data pipelines
- `supabase/migrations/`: account data schema and access policies
- `tests/`: backend contracts and recovery tests
- `run_all.py`, `run_daily_sync.py`: one-step API launch and explicit data refresh

Historical venue evidence uses the last five and ten qualifying matches when possible; unsupported venues use a labeled curated or neutral fallback. The report is descriptive until its predictive effect is backtested. Saved model and validated data backups are retained for recovery.
