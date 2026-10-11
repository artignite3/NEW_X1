# NEW_X1 website

The Next.js frontend is published as a static site at [new-x1.pages.dev](https://new-x1.pages.dev/). It shows fixtures, squad availability, the simulator, account controls and backend status. Match analysis comes from the separate FastAPI service.

From `frontend/`, run `npm ci` and `npm run dev` for local development. Copy `.env.example` to the ignored `.env.local` and configure the public values required by your environment. Build-time `NEXT_PUBLIC_*` values are visible in the browser, so never put secret credentials there.

Before publishing, run `npm run lint` and `npm run build:static`. The [Cloudflare Pages workflow](../.github/workflows/deploy-cloudflare-pages.yml) deploys frontend changes from `main`. The temporary backend URL can be entered in the site's **Settings** page; it must be running for ML analysis. See the root [README](../README.md) and [runbook](../docs/RUNBOOK.md) for operation.
