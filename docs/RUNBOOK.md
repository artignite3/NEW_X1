# NEW_X1 runbook

This is the current Cloudflare Pages and laptop-backend workflow. Run commands from the repository root. Use the [Cloudflare guide](CLOUDFLARE_DEMO.md) for the one-time GitHub/Supabase settings and tunnel details.

## Local setup

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements.txt
Set-Location frontend
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
Set-Location ..
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Fill credentials in the ignored `.env` files; never commit them. Model binaries and large source data are separate local artifacts and must be restored before inference or a full data refresh.

## Verify changes

```powershell
.\env\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
Set-Location frontend
npm run lint
npm run build:static
Set-Location ..
```

The [deployment workflow](../.github/workflows/deploy-cloudflare-pages.yml) runs `npm ci`, lint and the static build, then uploads the site on frontend changes pushed to `main`. Check the GitHub Actions result and the live site; a successful Git push alone does not prove a successful deployment.

## Start or stop the API

```powershell
.\scripts\start_cloudflare_demo.ps1 -ArtifactsRoot '<absolute path to artifact-holding checkout>' -SiteOrigin 'https://new-x1.pages.dev'
```

Keep the launcher open. Copy the HTTPS tunnel origin it prints into the website's **Settings** page. Stopping the launcher stops the backend and tunnel. A new tunnel session can have a new URL; refresh Settings in each browser. Check `http://127.0.0.1:8000/health` locally before testing the public site.

## Refresh data and backups

The launcher does not refresh fixtures or squads. On the artifact-holding checkout, run `data/future_matches/schedule_fetcher.py` for fixtures and `data/future_matches/squad_fetcher.py --max-requests 3` for a quota-bounded squad refresh. Run `run_daily_sync.py` when historical features and venue evidence need a full update. After a healthy install, `data_processing/seed_backups.py` can create missing validated last-good copies.

The API reports a feed warning or unavailable state when both current and backup data fail validation. Keep model archives, ingestion manifests and evaluation evidence; deleting them is not a routine cleanup step. See the [API reference](API_REFERENCE.md) for the fallback contract.

## Recovery

Use `git log` and the GitHub deployment history to identify a known-good revision. Restore model binaries from `model_artifacts/archive/` or another verified backup, then check `/health` and all three formats. For a data failure, refresh the affected feed or restore its validated last-good copy. The historical Render/AWS plan is retained [in the archive](archive/RENDER_DEPLOYMENT_GUIDE_2026-10-08.md).
