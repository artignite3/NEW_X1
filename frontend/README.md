# NEW_X1 website

The Next.js 16 interface provides upcoming fixtures, a custom T20/ODI/Test simulator, an account page, and backend settings. The public static build is hosted at [new-x1.pages.dev](https://new-x1.pages.dev/). Supabase powers sign-in; match analysis comes from the separate Python API and ML models.

## Run locally

From this directory, run `npm ci` and `npm run dev`, then open `http://localhost:3000`. Copy `.env.example` to `.env.local` and add the public Supabase URL and publishable key if using sign-in. `NEXT_PUBLIC_API_BASE` can point to a reachable backend; local development defaults to `http://localhost:8000`. Never put service-role credentials in `NEXT_PUBLIC_*` variables.

## Backend availability

The navigation checks `/health` with an eight-second timeout and rechecks periodically and when the browser regains focus. If the API is unreachable or its models are unavailable, a site-wide banner explains that the static website is still online and provides email and message links to request starting the laptop backend and ML engine. Once the backend responds with models, the banner disappears. Visitors can set their own current tunnel address on **Settings**; that override is stored in their browser. The public site needs a fresh static deployment if the build-time `NEXT_PUBLIC_API_BASE` changes.

## Build and publish

Run `npm run lint` and `npm run build:static`. Upload the **contents** of `out/` to the Cloudflare Pages Direct Upload project. A Git push alone does not update this deployment. See the [Cloudflare guide](../docs/CLOUDFLARE_DEMO.md) for the backend tunnel, fixture refresh, and deployment checks. The [Pitch Control plan](../docs/PITCH_CONTROL_REPORT_PLAN.md) explains how the venue report is sourced and where its predictive backtest remains open.
