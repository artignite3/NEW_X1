# NEW_X1 — first deployment, step by step

Prepared 8 October 2026. **Historical Render/AWS proposal; the current website is hosted on Cloudflare Pages.** These instructions are retained for a future managed deployment, not for the current live site. See the [current Cloudflare guide](../CLOUDFLARE_DEMO.md).

Verification boundary: the local Windows suite, real artifact restore/API boot, all-format strict generation, frontend build and standalone web/icon serving have passed. The Render Blueprint passes its published JSON schema. A local Linux backend build installed dependencies and passed `pip check`, then Docker failed to commit the layer because C: ran out of space and its filesystem became read-only. Container completion/tests, real AWS access, hosted CI, Supabase integration and public activation remain required checks; no live URL is claimed.

## Where each part goes

| Part | Service | Purpose |
|---|---|---|
| Website | Render Node web service | Hosts the Next.js interface and gives you a public HTTPS address |
| Backend | Render Docker web service | Runs FastAPI, predictions and team generation |
| Daily pipeline | Render Docker cron job | Refreshes histories/features/fixtures/squads and publishes a verified release |
| Login and saved results | Supabase Auth + Postgres | Google/email/optional phone login, MFA and private saved analyses |
| Model/data releases | Private AWS S3 bucket | Keeps large runtime files outside the laptop and Render's temporary disks |

This layout is a managed beta recommendation. Render compute, object storage, SMTP and optional SMS can incur charges. Review dashboard quotes and set budgets before activating paid services. The sample Blueprint uses a 2GB API instance, an 8GB pipeline job and a smaller website instance as starting sizes; hosted memory/load measurements may require changes. Do not select a 512MB API instance just to obtain a free URL for the full ML workload.

A domain purchase is optional. Render's assigned HTTPS address is enough for the first staging test. Supabase hosts authentication/database services; it does not deploy this FastAPI ML backend or Next.js website for you.

## Step 1 — create Supabase

1. Open [Supabase Dashboard](https://supabase.com/dashboard) and sign up, preferably with the GitHub account used for the repository.
2. Create an organization if prompted, then a project named **NEW_X1**. Select a region near your audience and save the database password privately.
3. Wait until the project is ready. Find its **Project URL** and **publishable key** in the project's connection/API settings. You may share the project URL; keep database passwords, service-role/secret keys and provider credentials private.
4. Open the project's SQL editor. Open `supabase/migrations/202610080001_accounts.sql` in this repository, paste its complete contents into a new query, and run it. Check for SQL errors. It creates saved-result/explanation tables, ownership policies and generation quotas. The setup can be rerun: it replaces its five named policies in the same transaction without deleting account data or disabling RLS.
5. Under Auth signing keys, use an asymmetric signing key (**ES256 or RS256**). A legacy HS256-only project will not pass this backend's session verification.

**Checkpoint:** you have a running project, its URL/publishable key, and a successful migration. No website deployment is needed for this step. Real SQL/RLS behavior must still be tested with two accounts later.

**Project checkpoint — 8 October 2026:** Supabase project `chvffwgzfkuvgepqpbtz` is connected locally through ignored environment files. The account migration completed and the dashboard verification showed RLS enabled with the expected policy counts (2 explanation, 0 direct quota and 3 saved-analysis policies). Live read-only checks returned Auth HTTP 200, email authentication enabled and one ES256 discovery key. A local email OTP sign-in and TOTP authenticator enrollment/verification completed successfully. The frontend production build passed with this configuration. The publishable key is deliberately absent from Git; add it to each deployment through the provider's environment settings. Google OAuth, two-account hosted RLS testing and public deployment remain pending.

If you see `42710: policy "own_explanations_select" ... already exists`, an earlier run created that policy. Replace the entire editor query with the current migration file and run the whole file, including `begin;` and `commit;`. Do not delete tables or disable RLS. A successful run alone is not a full login/RLS integration test.

The rerun fix was checked locally with PGlite (PostgreSQL compiled to WebAssembly) and simulated Supabase auth roles/identity: fresh setup, repeated execution, partial-policy repair, retained rows, unchanged policy definitions, RLS enabled, rollback on an injected error, two-user isolation, rejected cross-user writes/deletes, anonymous access rejection and the 20/day quota passed. The 12 Python account tests also passed. This does not establish that the hosted project's migration or Auth configuration is complete.

To confirm the setup after a successful run, execute this separate read-only query. Expect five rows with `rls_enabled=true`, covering two policies on `explanations` and three on `saved_analyses`:

```sql
select p.tablename, p.policyname, p.cmd, c.relrowsecurity as rls_enabled
from pg_policies p
join pg_namespace n on n.nspname = p.schemaname
join pg_class c on c.relnamespace = n.oid and c.relname = p.tablename
where p.schemaname = 'public'
  and p.tablename in ('explanations', 'saved_analyses')
order by p.tablename, p.policyname;
```

SQL Editor execution does not record CLI migration history. If you later adopt `supabase db push`, reconcile the manual setup with the CLI history first, following the [Supabase migration guide](https://supabase.com/docs/guides/deployment/database-migrations); do not reset the hosted database to resolve a history mismatch.

## Step 2 — create Render and connect GitHub

1. Open [Render Dashboard](https://dashboard.render.com/) and sign up with GitHub.
2. Allow access to the repository **artignite3/NEW_X1**. If it does not appear, update the Render GitHub application's repository permissions and refresh the list.
3. Keep service creation for Step 5. Do not create a separate Render Postgres database: this project uses Supabase Postgres for account data.

**Checkpoint:** Render can see the repository. Creating an account alone does not mean the project is deployed.

## Step 3 — prepare durable storage

The model files and historical datasets are intentionally absent from Git. A fresh host needs the artifact seed below; cloning Git alone cannot serve predictions.

1. Create an AWS account if necessary. In Amazon S3, create a uniquely named general-purpose bucket in a nearby region. Keep **Block all public access** enabled and enable **bucket versioning**. Record the bucket name and region.
2. Use IAM identities dedicated to this application, rather than root access keys. Create a reader identity for the API and a writer identity for local seeding/the scheduled worker.
3. Replace `REPLACE_WITH_BUCKET_NAME` in `deploy/iam-reader.json` and `deploy/iam-writer.json`. Attach those policies to the corresponding identities. The reader can get objects only; the writer can get/put objects under `new-x1/` and cannot delete them.
4. Store each identity's access key/secret in the relevant environment settings. Never put AWS credentials in frontend variables, the repository, screenshots or chat.
5. Set an AWS budget/notification and a retention policy that preserves the current and previous release. Do not expire content-addressed blobs merely because they are old: newer manifests can still reference them. Database backups need their own Supabase policy.

This implementation targets AWS S3 conditional writes. Supabase Storage or other S3-compatible services are not interchangeable without compatibility testing. Only trusted artifact writers should have upload access because model joblib files contain executable serialized objects.

**Checkpoint:** private bucket/versioning exists, and you have separate read/write credentials. For service setup, `AWS_DEFAULT_REGION` must be the bucket's region, even if Render runs in another region.

## Step 4 — seed the models and data from this laptop

Use PowerShell in the repository directory:

```powershell
Set-Location 'D:\Personal Coding\Data Science and ML\NEW_X1'
env/Scripts/python.exe -m pip install -r requirements.txt
env/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'
env/Scripts/python.exe -m pipeline.validate_release --root .
```

Your local `.env` already exists. **Edit it; do not replace it with the example and lose existing provider configuration.** Add `RELEASE_BUCKET`, `RELEASE_PREFIX=new-x1`, `AWS_DEFAULT_REGION`, and the **writer** access key/secret. Keep `.env` untracked. Ensure `RELEASE_STORE_DIR` is absent when seeding AWS; that setting selects the offline test adapter.

Stop any local ingestion/training run before seeding. Then run:

```powershell
env/Scripts/python.exe -m pipeline.releases seed --root .
env/Scripts/python.exe -m pipeline.releases restore --cache outputs/cloud_restore_check
```

The first command validates a frozen snapshot, uploads checksummed blobs and promotes a release manifest. The second downloads/checks/validates it from AWS. A nonzero exit or `fallback_used=true` requires investigation before deployment. Save the release ID. Do not upload `.env`, raw archives, the virtual environment or account SQLite files.

**Checkpoint:** an initial complete release can be restored from the private bucket. The local offline adapter has passed this drill; real AWS permissions/network remain an activation check.

## Step 5 — deploy the backend first

For a first deployment, creating the services individually makes it easier to discover the correct URLs. `render.yaml` is also available for later Blueprint management, after environment values/URLs are known.

1. In Render choose **New → Web Service**, select the NEW_X1 repository, and use branch `main`.
2. Name it `new-x1-api`. Choose a nearby region (the reference setup uses Singapore). Leave Root Directory empty, select **Docker**, and use the root `Dockerfile`.
3. Review the instance quote; the reference starting point is 2GB RAM. Set the health-check path to `/live` and allow at least 120 seconds for graceful shutdown.
4. Add these environment values:

| Variable | Value |
|---|---|
| `APP_ENV` | `staging` |
| `SUPABASE_URL` | Project URL from Step 1 |
| `SUPABASE_PUBLISHABLE_KEY` | Publishable key from Step 1 |
| `RELEASE_BUCKET` | Bucket name |
| `RELEASE_PREFIX` | `new-x1` |
| `AWS_DEFAULT_REGION` | Bucket region |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | API **reader** identity |
| `RELEASE_POLL_SECONDS` | `300` |
| `PHONE_AUTH_ENABLED` | `false` initially |
| `CORS_ORIGINS` | Your website origin once known; temporarily `http://localhost:3000` for local staging checks |

5. Deploy and inspect logs. Startup restores/validates the release before opening the API port. Save the actual assigned HTTPS API URL; do not assume the service name guarantees a particular hostname.
6. Visit `/live`, `/ready`, `/health` and `/matches` on that URL. Liveness must return 200; readiness needs configured authentication and a verified release created within 72 hours. `/health` reports models, fallback/source information, pipeline status and latest historical match dates. A fresh release timestamp does not prove the historical source has recent matches.

The API intentionally uses one inference process and bounded analysis capacity for this beta. Busy data requests return 503 with Retry-After rather than racing shared caches. `/live` remains available during analysis. Do not set `APP_ENV=development` on a public service to bypass authentication.

**Checkpoint:** public API health/readiness works with the seeded private artifacts. Authenticated generation is checked after login setup.

## Step 6 — deploy the website and finish login addresses

1. Create another Render **Web Service** from the same repository/branch. Name it `new-x1-web`, choose **Node**, and set Root Directory to `frontend`.
2. Build command: `npm ci && npm run build && npm run prepare:standalone`.
3. Start command: `node .next/standalone/server.js`.
4. Set `NODE_VERSION=22`, `HOSTNAME=0.0.0.0`, `NEXT_PUBLIC_API_BASE` to the actual HTTPS API URL, and `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` to Step 1's values. Set `NEXT_PUBLIC_PHONE_AUTH_ENABLED=false` initially. `API_INTERNAL_BASE` is optional; omit it to use the public API address rather than a laptop-local address.
5. Deploy, save its actual HTTPS website URL, and visit it. The navigation logo, favicon and fixtures should load. Update backend `CORS_ORIGINS` to this exact origin without a trailing path, and redeploy/restart the backend as required by Render.
6. In Supabase Auth URL settings, set **Site URL** to the website URL and add the exact `https://YOUR-WEBSITE/account` redirect. Add localhost redirects only if you need local testing; avoid broad production wildcards.
7. Configure Google OAuth and enable the Google provider using [Supabase's Google guide](https://supabase.com/docs/guides/auth/social-login/auth-google). Google's redirect URI is the **Supabase callback URL**, while Supabase's allowed frontend redirect is your website's `/account` address. Enable manual identity linking if using the Link Google button.
8. For email code entry, configure SMTP and put `{{ .Token }}` in both the **Confirm signup** and **Magic link or OTP** templates. First-time and returning users can use different templates; changing only the magic-link template can leave new users with a confirmation link while the UI waits for a code. Supabase currently sends eight-digit email OTPs (the UI also accepts six-digit legacy codes). Supabase's default SMTP has restricted delivery; use [production SMTP](https://supabase.com/docs/guides/auth/auth-smtp) before public email OTP. Optional phone login needs a configured/tested SMS provider and both frontend/backend flags enabled. Enroll TOTP from Account and verify after a fresh sign-in.

Public frontend variables are bundled at build time. **Rebuild the website** when changing public API/Supabase values or the phone flag. Follow [AUTH_SETUP.md](../AUTH_SETUP.md) for detailed MFA, OTP and account checks.

**Checkpoint:** Google/email login completes and returns to Account; a signed-in user can generate, explain, save and reload an analysis. Use two accounts to verify isolation. No such real-provider journey is claimed verified before this step.

## Step 7 — deploy and test the daily pipeline

1. Create a Render **Cron Job** using the same repository, root Dockerfile and branch.
2. Command: `python -m pipeline.worker`.
3. Schedule: `30 20 * * *`, meaning daily **02:00 Asia/Calcutta**. Render schedules use UTC.
4. Set `APP_ENV=staging`, the bucket/prefix/region, the **writer** AWS credentials, `RAPID_API_KEY`, `CRICKET_DATA_API_KEY`, and `SQUAD_REQUEST_BUDGET=3`. The reference initial worker size is 8GB because historical feature updates are heavier than inference; review the job quote and measure memory.
5. Trigger one manual run. It restores the previous release, works in private scratch space, downloads/ingests/updates data, refreshes fixtures/squads and validates before promotion. A required-stage failure preserves the release pointer. Optional provider failures are recorded as degraded and return a failing job exit for notification, while retaining usable data.
6. Allow up to five minutes for the API's artifact poll, then inspect health/release ID and fixtures. Configure failed-job notifications and external checks for `/ready` and stale/degraded `/health`. Set provider budgets appropriate to the desired squad coverage; a three-request squad cap does not guarantee every match is covered.

The daily job updates data/features; it does not automatically retrain/promote models. New models still require baseline evaluation and a validated release. If the scheduler stops long enough, readiness becomes unavailable rather than declaring indefinitely fresh data.

**Checkpoint:** a real scheduled run promotes a release and the API serves it; an injected failure preserves the prior release and triggers notification.

## Recovery and public-beta gate

With writer credentials and no offline-store override:

```powershell
env/Scripts/python.exe -m pipeline.releases rollback
env/Scripts/python.exe -m pipeline.releases restore --cache outputs/recovery_check
```

Rollback validates the previous release and changes the pointer conditionally. The API sees it on its next poll. On current-release corruption, bootstrap can use the complete previous valid release; if neither validates, startup refuses to serve. Account storage never bypasses identity or falls back to local SQLite in production.

Before opening public access, record the real login/save journey, three-format generation, provider failure, restore, quota, RLS, OTP/MFA, latency/memory and monitoring checks. Arrange account recovery/deletion support, database backups, expired-record cleanup and privacy/retention terms. Uncertainty remains uncalibrated; full scoring/idempotency and player identity gates also remain open in the verdict.

## If you get stuck

- Repository missing: check Render's GitHub app access to this repository.
- API exits before opening a port: confirm the seeded release and reader permissions; check logs for release validation failure. Never solve this by making the bucket public.
- HTTP 503 on `/ready`: verify Supabase settings and release freshness; HTTP 503 on a data route with Retry-After can mean analysis capacity is busy.
- Fixtures show unavailable: check API address, backend health, provider feed freshness and missing squad coverage.
- Google redirects to localhost: update Supabase Site URL and allowed `/account` redirect; verify Google's Supabase callback separately.
- Login works but save fails: check migration/RLS, session/MFA status and account database availability.
- Website uses an old API address: rebuild after updating `NEXT_PUBLIC_API_BASE`; remove an incorrect `API_INTERNAL_BASE`.

Provider references: [Render Next.js](https://render.com/docs/deploy-nextjs-app), [Blueprint fields](https://render.com/docs/blueprint-spec), [cron jobs](https://render.com/docs/cronjobs), [Supabase redirects](https://supabase.com/docs/guides/auth/redirect-urls), [AWS S3 setup](https://docs.aws.amazon.com/AmazonS3/latest/userguide/GetStartedWithS3.html).
