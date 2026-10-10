# Cloudflare Pages + laptop backend

This no-card setup publishes the Next.js interface on Cloudflare Pages and serves the ML API from this laptop through a temporary Cloudflare Quick Tunnel. The website stays online; ML features work while the laptop and tunnel are running. Quick Tunnels are for demos and their URL changes on restart.

## Publish the website

1. Sign in to [Cloudflare Dashboard](https://dash.cloudflare.com/) and open **Workers & Pages → Create → Pages → Connect to Git**. Select GitHub repository `artignite3/NEW_X1` and branch `main`.
2. Set project root to `frontend`, build command to `npm run build:static`, and output directory to `out`. Set `NODE_VERSION=22` if the default is older.
3. Under build environment variables, set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` to the project's Supabase URL and publishable key. Leave `NEXT_PUBLIC_API_BASE` unset because the Quick Tunnel address changes. Set `NEXT_PUBLIC_PHONE_AUTH_ENABLED=false` until phone login is ready.
4. Deploy and record the assigned `https://<project>.pages.dev` address. On the Cloudflare site, `/`, `/simulator`, `/account`, and `/settings` should all load. Set Supabase Auth's Site URL to the Pages URL and add `https://<project>.pages.dev/account` to the allowed redirects.

## Start the laptop API and tunnel

1. Install Cloudflare's `cloudflared` once. On Windows, `winget install --id Cloudflare.cloudflared --exact --source winget` is one option. Reopen PowerShell so the command is on PATH.
2. Keep `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` configured in the local `.env` beside the model artifacts. The launcher sets `APP_ENV=staging` and allows the exact Pages origin through CORS.
3. From this repository, start the API and tunnel together:

   ```powershell
   .\scripts\start_cloudflare_demo.ps1 -ArtifactsRoot 'D:\Personal Coding\Data Science and ML\NEW_X1' -SiteOrigin 'https://YOUR-PROJECT.pages.dev'
   ```

4. The terminal prints an `https://...trycloudflare.com` address. Open the Pages website's **Settings**, paste that origin, and select **Save and test connection**. Refresh Fixtures after a successful test. Each browser stores its own tunnel URL, so other visitors must enter it on their own devices.
5. Leave the terminal open. Stopping the command stops the tunnel and API. On the next start, paste the newly assigned URL into Settings.

The API process binds only to `127.0.0.1`; Cloudflare makes it reachable externally through the tunnel. Anyone who learns the Quick Tunnel address can request public API routes. Supabase authentication remains required for account-protected operations. This temporary setup is unsuitable as an always-on production service.

Sources: [Cloudflare static Next.js guide](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/), [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [cloudflared downloads](https://developers.cloudflare.com/tunnel/downloads/).
