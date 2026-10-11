# Account migration

[`202610080001_accounts.sql`](202610080001_accounts.sql) creates the tables, policies and quota function used by the account API. Review it before applying through Supabase CLI or SQL Editor, especially if tables or policies were created manually. The migration intentionally restricts per-user rows with RLS; schema changes are live infrastructure operations and require the project operator.

Validate with the fixed-data [auth tests](../../tests/README.md), then run the live cross-user/RLS and quota checks described in [auth setup](../../docs/AUTH_SETUP.md). This folder contains source SQL, not credentials or a database dump.
