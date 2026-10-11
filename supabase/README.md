# Supabase account schema

[`migrations/`](migrations/README.md) defines user-owned explanation and saved-analysis rows, row-level policies and an atomic daily generation quota. The browser uses a public publishable key; the FastAPI service validates user JWTs and accesses rows using that user's bearer token. Never put a service-role key in frontend variables.

Apply migrations to a selected Supabase project only after reviewing its existing schema and migration history. Local unit tests cover JWT rejection and ownership logic but cannot prove live RLS, Google/email/phone delivery or MFA behavior. See the [activation guide](../docs/AUTH_SETUP.md) and [root setup](../README.md).
