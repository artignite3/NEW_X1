# Current audit (11 October 2026)

This is the live evidence set for the source checkout on `pitch-control-report`. Read the [verification results](VERIFICATION.md), [issue register](ISSUES.md), and [release verdict](RELEASE_READINESS.md) together. Earlier notes under [`docs/archive/`](../archive/README.md) are dated history, not the current verdict. The [root README](../../README.md) and [documentation index](../README.md) explain setup and navigation.

## Documentation inventory

Meaningful source and configuration folders have local guides: root; `.github` and `.github/workflows`; `data` and `data/future_matches`; `data_processing`; `data_preprocessing`; `deploy`; `design` and `design/brand`; `docs`, `docs/audit`, and `docs/archive`; `frontend`, `frontend/src`, its `app`, `components` and `lib`, and `frontend/scripts`; `intelligence`; `model`; `model_artifacts`; `pipeline`; `scripts`; `supabase` and `supabase/migrations`; `tests`; `UI` and `UI/components`. `video_launch` and `video_launch/motion_enhanced` already have their own READMEs and are pre-existing untracked user work in this checkout. `out_of_sample_data` is an ignored empty placeholder.

No extra README was added to generated, public-asset, or dependency folders such as `env`, `frontend/node_modules`, `.next`, `frontend/out`, `frontend/public`, `outputs`, `data/raw`, `data/interim`, `data/processed`, `out_of_sample_data`, `__pycache__`, or model archive timestamp folders. They are explained by their parent guides. The Markdown checker scans current documentation by default; `--include-archive` also checks historical notes.

## Audit scope and boundaries

The review followed the Next.js browser client through FastAPI authentication, fixture/squad data, model inference, optimization, venue intelligence, snapshot recovery, the one-step launcher, CI and static deployment configuration. Fixed-data tests, local model loading and static builds were executed. Live Supabase RLS/provider flows, a public tunnel session, Cloudflare deployment and future-match predictive validity require external integration evidence and are not claimed here. Existing uncommitted frontend/backend/video work was preserved; the audit did not commit, push or deploy.

## Changes prepared in this worktree

- Updated the [root README](../../README.md), [API reference](../API_REFERENCE.md), [auth guide](../AUTH_SETUP.md), legacy preprocessing guide and documentation index to match the checked code and remote branch state.
- Added purpose-specific folder READMEs for source, tests, operations, configuration and archived/model material; kept generated and publicly served asset directories free of extra documentation files.
- Added [`scripts/check_docs.py`](../../scripts/check_docs.py) and [`scripts/smoke_local.py`](../../scripts/smoke_local.py) so link and local inference checks are repeatable.
- Bounded future `fetched_at` metadata in the [fixture](../../data/future_matches/fixture_store.py) and [squad](../../data/future_matches/squad_store.py) stores and added two backup regression tests.
- Recorded the actual checks and remaining gates in [verification](VERIFICATION.md), [issues](ISSUES.md) and [release readiness](RELEASE_READINESS.md).
