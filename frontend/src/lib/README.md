# Browser clients and types

[`api.ts`](api.ts) chooses the API origin from browser Settings or a build-time public value, validates an HTTPS origin for remote use, and calls FastAPI with timeouts and session headers. [`auth.ts`](auth.ts) configures the Supabase browser client and retrieves the current access token. [`types.ts`](types.ts) describes API response shapes consumed by pages/components.

Only publishable Supabase values belong in `NEXT_PUBLIC_*`; never send a service-role credential to this client. A temporary tunnel URL is stored in each browser and must be updated after restart. Run `npm run lint` and `npm run build:static` from [`frontend`](../../README.md). See [backend API contract](../../../docs/API_REFERENCE.md).
