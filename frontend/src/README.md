# Website source

[`app/`](app/README.md) defines static-export pages and global layout, [`components/`](components/README.md) holds reusable presentation and analysis panels, and [`lib/`](lib/README.md) holds the API/auth clients and shared types. The website is built with Next.js and React; browser calls reach the separate FastAPI tunnel and Supabase.

Use `npm run dev` from [`frontend/`](../README.md) for local development and `npm run lint` plus `npm run build:static` before publishing. Build-time `NEXT_PUBLIC_*` values are public. See the [Cloudflare guide](../../docs/CLOUDFLARE_DEMO.md).
