# Application routes

`page.tsx` displays fixtures, `simulator/page.tsx` runs custom analysis, `account/page.tsx` handles login/MFA and saved analyses, and `settings/page.tsx` stores/tests the current API origin. `layout.tsx` and `globals.css` define common shell/styles. These client pages are included in the static export; the API and Supabase remain external services.

Run `npm run lint` and `npm run build:static` from [`frontend`](../../README.md). A successful static build does not prove live OAuth, provider data or public tunnel reachability. See the [API guide](../../../docs/API_REFERENCE.md) and [auth setup](../../../docs/AUTH_SETUP.md).
