# NEW_X1 runbook

This is the current Cloudflare Pages and laptop-backend workflow. For a cloud server instead of the laptop, see [deploy/oracle](../deploy/oracle/README.md). Run commands from the repository root.

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
.
un_all.bat
```

The launcher finds a sibling `NEW_X1` artifact checkout on this laptop. For another layout, use `python run_all.py --artifacts-root '<absolute artifact checkout path>'`. It starts the inference API, opens a public tunnel and publishes the tunnel address to Supabase, so the website connects on its own. A restarted tunnel publishes its new address, and visitors' pages pick it up at their next health check. Stopping the launcher clears the address, so the site shows the server as offline straight away. Check `http://127.0.0.1:8000/health` locally before testing the public site.

If publishing is not configured, the launcher prints the **PUBLIC API** address; paste it into the website's **Settings** page as a manual override.

If the network blocks both tunnels, the runner keeps the API local and retries every 60 seconds. Run `run_all.bat --local-only` to skip tunnel attempts. Local-only operation does not give the Cloudflare website a public API address.

### Start automatically at sign-in

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1          # install
Start-ScheduledTask -TaskName "NEW_X1 backend"                                   # start now
Get-Content outputs\launcher.log -Wait -Tail 20                                 # status and tunnel address
Get-Content outputs\launcher.err.log -Wait -Tail 20                             # server request log
powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1 -Remove  # uninstall
```

The task runs the launcher hidden whenever you are signed in, restarts it after a crash and writes status to `outputs/launcher.log` and server logs to `outputs/launcher.err.log`, both fresh at each sign-in. After changing the installer, run it again to update the task.

### One-time address publishing setup

1. In the Supabase SQL editor, run `supabase/migrations/202611250001_backend_endpoint.sql`.
2. Put a long random `NEW_X1_PUBLISH_TOKEN` in the artifact checkout's `.env` (for example `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
3. Register its hash, replacing `<sha256 hex>` with the output of `python -c "import hashlib; print(hashlib.sha256('<token>'.encode()).hexdigest())"`:

```sql
insert into private.backend_publisher (id, token_sha256) values (1, '<sha256 hex>')
  on conflict (id) do update set token_sha256 = excluded.token_sha256;
```

Anyone can read the published address, which is public anyway; only the token holder can change it. To rotate the token, repeat steps 2 and 3.

## Refresh data and backups

The launcher does not refresh fixtures or squads. On the artifact-holding checkout, run `data/future_matches/schedule_fetcher.py` for fixtures and `data/future_matches/squad_fetcher.py --max-requests 4` for a quota-bounded squad refresh. Run `run_daily_sync.py` when historical features and venue evidence need a full update. After a healthy install, `data_processing/seed_backups.py` can create missing validated last-good copies.

The API reports a feed warning or unavailable state when both current and backup data fail validation. Keep model archives, ingestion manifests and evaluation evidence; deleting them is not a routine cleanup step. See the [API reference](API_REFERENCE.md) for the fallback contract.

## Recovery

Use `git log` and the GitHub deployment history to identify a known-good revision. Restore model binaries from `model_artifacts/archive/` or another verified backup, then check `/health` and all three formats. For a data failure, refresh the affected feed or restore its validated last-good copy.
