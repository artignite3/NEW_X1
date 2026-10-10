# Cloudflare Pages + laptop backend

This no-card setup publishes the Next.js interface on Cloudflare Pages and serves the ML API from this laptop through a temporary HTTPS tunnel. The website stays online; ML features work while the laptop and tunnel are running. Tunnel URLs change on restart.

## Publish the website

1. Sign in to [Cloudflare Dashboard](https://dash.cloudflare.com/) and open **Workers & Pages → Create → Pages → Direct Upload**. The current project name is `new-x1`, giving `https://new-x1.pages.dev`.
2. In `frontend/.env.local`, set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` to the project's public values. You may set `NEXT_PUBLIC_API_BASE` to the current tunnel origin to make the API work for all visitors immediately. Set `NEXT_PUBLIC_PHONE_AUTH_ENABLED=false` until phone login is ready. This file is ignored by Git.
3. Run `npm ci` once, then `npm run build:static` in `frontend`. Zip the *contents* of `frontend/out`, with `index.html` at the zip root. Upload that zip to the Pages project and select **Save and deploy**. A Git push alone does not update a Direct Upload project.
4. Check `/`, `/simulator`, `/account`, and `/settings` on `https://new-x1.pages.dev`. Supabase Auth's Site URL is set to this Pages URL, with `https://new-x1.pages.dev/account` allowed as a redirect; the localhost account redirect remains for development. A fresh Google sign-in on the deployed site completed on 10 October 2026. Reused OAuth callbacks can report `flow_state_already_used`; start a new sign-in from `/account` instead of reopening the old callback.

## Start the laptop API and tunnel

1. For the Cloudflare tunnel, install `cloudflared` once. On Windows, `winget install --id Cloudflare.cloudflared --exact --source winget` is one option. Reopen PowerShell so the command is on PATH. The `LocalhostRun` fallback uses Windows OpenSSH instead.
2. Keep `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` configured in the local `.env` beside the model artifacts. The launcher sets `APP_ENV=staging` and allows the exact Pages origin through CORS.
3. From this repository, start the API and tunnel together:

   ```powershell
   .\scripts\start_cloudflare_demo.ps1 -ArtifactsRoot 'D:\Personal Coding\Data Science and ML\NEW_X1' -SiteOrigin 'https://YOUR-PROJECT.pages.dev'
   ```

4. The terminal prints a temporary HTTPS address. If the current Pages build has no `NEXT_PUBLIC_API_BASE`, open the website's **Settings**, paste the tunnel origin, and select **Save and test connection**. Refresh Fixtures after a successful test. Each browser saves this override separately. To serve the same address automatically to all visitors, put it in `frontend/.env.local` as `NEXT_PUBLIC_API_BASE`, rebuild and redeploy the static site.
5. Leave the terminal open. Stopping the command stops the tunnel and API. On the next start, paste the newly assigned URL into Settings. The URL baked into a prior static build will be stale until that build is redeployed.

If this network blocks `api.trycloudflare.com`, use the same static Cloudflare Pages site with the account-free [localhost.run](https://localhost.run/) tunnel:

```powershell
.\scripts\start_cloudflare_demo.ps1 -ArtifactsRoot 'D:\Personal Coding\Data Science and ML\NEW_X1' -SiteOrigin 'https://YOUR-PROJECT.pages.dev' -TunnelProvider LocalhostRun
```

OpenSSH remembers the SSH server key on first use; a changed key stops the connection. This fallback URL may end in `.lhr.life` or another hostname shown by the tunnel and changes over time. If a browser security interstitial appears, do not bypass it; use the Cloudflare tunnel after your DNS administrator allows it.

The API process binds only to `127.0.0.1`; the selected tunnel makes it reachable externally. Anyone who learns the tunnel address can request public API routes. Supabase authentication remains required for account-protected operations. This temporary setup is unsuitable as an always-on production service.

## Keep fixture data current

The launcher starts the API and tunnel; it does not fetch new cricket data. From the checkout that holds your `.env` and `data` directory, run the fixture fetcher when the feed is stale:

```powershell
Set-Location 'D:\Personal Coding\Data Science and ML\NEW_X1'
.\env\Scripts\python.exe data/future_matches/schedule_fetcher.py
```

The API reads the updated file on the next `/matches` or `/health` request. If the provider fails, the API keeps serving only still-future matches from the verified last-good snapshot and reports the warning. Squads have a separate feed; refreshing fixtures does not refresh squads. The squad fetcher uses a bounded provider-request budget:

```powershell
.\env\Scripts\python.exe data/future_matches/squad_fetcher.py --max-requests 3
```

Check `/health` afterward. A partial squad refresh can still leave matches without usable squads. This laptop setup has no automatic daily sync, so rerun the refresh while the laptop is online.

Sources: [Cloudflare static Next.js guide](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/), [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [cloudflared downloads](https://developers.cloudflare.com/tunnel/downloads/).
