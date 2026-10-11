# Build helpers

[`build-static.mjs`](build-static.mjs) invokes Next with `NEXT_OUTPUT=export` so Cloudflare Pages receives `frontend/out`. [`prepare-standalone.mjs`](prepare-standalone.mjs) packages the optional standalone server output used by the container/CI path. The public Pages deployment uses the static export, not a Node server.

Run `npm run build:static` or `npm run prepare:standalone` from [`frontend`](../README.md) after `npm ci`. GitHub Actions calls the static build in the [deployment workflow](../../.github/workflows/README.md). Build-time public variables are embedded in output.
