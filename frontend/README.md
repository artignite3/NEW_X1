# NEW_X1 website

The Next.js 16 interface provides upcoming fixtures, a custom T20/ODI/Test simulator, an account page, and backend settings. The public static build is hosted at [new-x1.pages.dev](https://new-x1.pages.dev/). Supabase powers sign-in; match analysis comes from the separate Python API and ML models.

Source navigation: [`src/app`](src/app/README.md) defines routes, [`src/components`](src/components/README.md) renders the fixture/analysis/account panels, [`src/lib`](src/lib/README.md) holds browser API/auth clients and types, and [`scripts`](scripts/README.md) contains build helpers. `public/brand` contains deployed image assets; its source notes are in [`design/brand`](../design/brand/README.md).

## Run locally

From this directory, run `npm ci` and `npm run dev`, then open `http://localhost:3000`. Copy `.env.example` to `.env.local` and add the public Supabase URL and publishable key if using sign-in. `NEXT_PUBLIC_API_BASE` can point to a reachable backend; local development defaults to `http://localhost:8000`. Never put service-role credentials in `NEXT_PUBLIC_*` variables.

## Backend availability

The navigation checks `/health` with an eight-second timeout and rechecks periodically and when the browser regains focus. If the API is unreachable or its models are unavailable, a site-wide banner explains that the static website is still online and provides email and message links to request starting the laptop backend and ML engine. Once the backend responds with models, the banner disappears. Visitors can set their own current tunnel address on **Settings**; that override is stored in their browser. The public site needs a fresh static deployment if the build-time `NEXT_PUBLIC_API_BASE` changes.

## Build and publish

Run `npm run lint` and `npm run build:static`. The [GitHub Actions workflow](../.github/workflows/deploy-cloudflare-pages.yml) uploads `out/` to the existing Cloudflare Pages Direct Upload project on pushes to `main` after its deployment secrets and public build variables are configured. Until then, upload the **contents** of `out/` manually. See the [Cloudflare guide](../docs/CLOUDFLARE_DEMO.md) for one-time GitHub setup, the backend tunnel, fixture refresh, and deployment checks. The [Pitch Control plan](../docs/PITCH_CONTROL_REPORT_PLAN.md) explains how the venue report is sourced and where its predictive backtest remains open.
