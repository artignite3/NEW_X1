# Cloudflare Pages + laptop backend

This no-card setup publishes the Next.js interface on Cloudflare Pages and serves the ML API from this laptop through a temporary HTTPS tunnel. The website stays online; ML features work while the laptop and tunnel are running. Tunnel URLs change on restart.

When the API is offline, times out, or has no usable ML models, every website page shows a contact notice. Visitors can request that the backend be started by [email](mailto:riddhu.work@gmail.com?subject=NEW_X1%20backend%20request) or [message](https://wa.me/918982094147). The notice clears after a successful health check.

## Connect GitHub pushes to the existing Pages site

Cloudflare does not allow converting this `new-x1` Direct Upload project to its native Git integration. The repository's [deployment workflow](../.github/workflows/deploy-cloudflare-pages.yml) instead uses GitHub Actions and Wrangler to publish a static build to the **same** `new-x1.pages.dev` site whenever frontend files are pushed to `main`. The workflow can also be started manually from GitHub's **Actions** tab.

One-time setup in the GitHub repository `artignite3/NEW_X1`:

1. In Cloudflare, create a scoped API token with **Account → Cloudflare Pages → Edit** permission for the account containing `new-x1`. Copy the account ID from your Cloudflare account dashboard. Keep the token out of the repository and chat.
2. In GitHub, open **Settings → Secrets and variables → Actions → Secrets**. Add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as repository secrets.
3. In the adjacent **Variables** tab, add `NEXT_PUBLIC_SUPABASE_URL` (the project's public Supabase URL) and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (its public publishable key). Optionally add `NEXT_PUBLIC_API_BASE` only when there is a stable HTTPS backend URL; for a changing laptop tunnel, leave it unset and use the site's **Settings** page per browser.
4. Open **Actions → Deploy website to Cloudflare Pages → Run workflow**, choose `main`, and wait for the build and deployment to pass. Verify the contact notice on the live site while the backend is offline. Later frontend pushes to `main` trigger this workflow automatically. Missing settings stop the workflow before deployment with a named error.

The publishable Supabase key is designed for browser use; never add a Supabase service-role key to these public variables. This workflow publishes the website only; it does not start the laptop backend or refresh fixture feeds.

## Publish the website manually

1. Sign in to [Cloudflare Dashboard](https://dash.cloudflare.com/) and open the existing **Workers & Pages → new-x1** project at `https://new-x1.pages.dev`.
2. In `frontend/.env.local`, set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` to the project's public values. You may set `NEXT_PUBLIC_API_BASE` to the current tunnel origin to make the API work for all visitors immediately. Set `NEXT_PUBLIC_PHONE_AUTH_ENABLED=false` until phone login is ready. This file is ignored by Git.
3. For a manual deployment, run `npm ci` once, then `npm run build:static` in `frontend`. Zip the *contents* of `frontend/out`, with `index.html` at the zip root. Upload that zip to the Pages project and select **Save and deploy**. Once the GitHub workflow above is configured, pushes to `main` deploy automatically instead.
4. Check `/`, `/simulator`, `/account`, and `/settings` on `https://new-x1.pages.dev`. Supabase Auth's Site URL is set to this Pages URL, with `https://new-x1.pages.dev/account` allowed as a redirect; the localhost account redirect remains for development. A fresh Google sign-in on the deployed site completed on 10 October 2026. Reused OAuth callbacks can report `flow_state_already_used`; start a new sign-in from `/account` instead of reopening the old callback.

## Start the laptop API and tunnel

1. For the Cloudflare tunnel, install `cloudflared` once. On Windows, `winget install --id Cloudflare.cloudflared --exact --source winget` is one option. Reopen PowerShell so the command is on PATH. The `LocalhostRun` fallback uses Windows OpenSSH instead.
2. Keep `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` configured in the local `.env` beside the model artifacts. The launcher sets `APP_ENV=staging` and allows the exact Pages origin through CORS.
3. From this repository, start the API and tunnel together:

   ```powershell
   .\run_all.bat
   ```

   The launcher automatically finds a sibling `NEW_X1` artifact checkout on this laptop. In another layout, pass `--artifacts-root` to `run_all.py`. It verifies all three ML models, tries Cloudflare over HTTP/2 first, then localhost.run, and retries later without stopping the local API if both fail. It prints `PUBLIC API` only after the public health check succeeds.

4. The terminal prints a temporary HTTPS address. If the current Pages build has no `NEXT_PUBLIC_API_BASE`, open the website's **Settings**, paste the tunnel origin, and select **Save and test connection**. Refresh Fixtures after a successful test. Each browser saves this override separately. To serve the same address automatically to all visitors, put it in `frontend/.env.local` as `NEXT_PUBLIC_API_BASE`, rebuild and redeploy the static site.
5. Leave the terminal open. Stopping the command stops the tunnel and API. On the next start, paste the newly assigned URL into Settings. The URL baked into a prior static build will be stale until that build is redeployed.

To use only the account-free [localhost.run](https://localhost.run/) tunnel instead of automatic fallback:

```powershell
.\run_all.bat --tunnel localhost-run
```

OpenSSH remembers the SSH server key on first use; a changed key stops the connection. This fallback URL may end in `.lhr.life` or another hostname shown by the tunnel and changes over time. If a browser security interstitial appears, do not bypass it; use the Cloudflare tunnel after your DNS administrator allows it.

If both tunnel hosts fail DNS resolution, inspect the network's DNS filter or ask its administrator to allow `api.trycloudflare.com` and `localhost.run`. An address of `0.0.0.0` for either host indicates a blocked lookup. Cloudflare Tunnel also needs outbound TCP port 7844; this launcher uses HTTP/2 because QUIC/UDP timed out on this laptop's network. A temporary URL that returns HTTP 530 is not a working backend, so the launcher retries instead of announcing it. You can still verify the models locally with `run_all.bat --local-only`; check `http://127.0.0.1:8000/health`. Do not put `127.0.0.1` or `localhost` in the deployed website's Settings: visitors' browsers would point to their own computers.

The API process binds only to `127.0.0.1`; the selected tunnel makes it reachable externally. Anyone who learns the tunnel address can request public API routes. Supabase authentication remains required for account-protected operations. This temporary setup is unsuitable as an always-on production service.

## Keep fixture data current

The launcher starts the API and tunnel; it does not fetch new cricket data. From the checkout that holds your `.env` and `data` directory, run the fixture fetcher when the feed is stale:

```powershell
Set-Location '<absolute path to artifact-holding checkout>'
.\env\Scripts\python.exe data/future_matches/schedule_fetcher.py
```

The API reads the updated file on the next `/matches` or `/health` request. If the provider fails, the API keeps serving only still-future matches from the verified last-good snapshot and reports the warning. Squads have a separate feed; refreshing fixtures does not refresh squads. Run the current squad fetcher from this source checkout; the wrapper uses the sibling artifact checkout's data, Python environment, and private API key with a bounded provider-request budget:

```powershell
.\refresh_squads.bat --max-requests 4
```

Check `/matches` afterward. `squad_source: provider` means a roster is saved for that match. `series_squad` means both teams' provider rosters were found in other matches from the same series and format; the website labels them **Series squads**, with an unconfirmed-XI warning. `last_match` means a provisional pool from each team's last complete same-format historical XI, with dates in `squad_match_dates`; `pending` means none of these sources can supply both teams. A successful `/health` does not imply every fixture has squads. The refresh skips fixtures covered by saved match or series rosters and limits provider calls; its exit code 3 means some fixtures remain without provider coverage. To retry one fixture, run `.\refresh_squads.bat --ids 174093 --max-requests 4`. An explicit ID also refreshes an existing provider squad. Some upcoming teams may have no published provider roster or complete historical XI, so repeated fetches cannot guarantee coverage. The Custom Simulator uses historical team rosters without requiring an upcoming match squad. This laptop setup has no automatic daily sync, so rerun the refresh while the laptop is online.

Sources: [Cloudflare static Next.js guide](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/), [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [cloudflared downloads](https://developers.cloudflare.com/tunnel/downloads/).
