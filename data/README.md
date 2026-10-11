# Data layout

[`future_matches/`](future_matches/README.md) contains fixture/squad fetchers and their validated JSON snapshots. `venue_history.json` is the compact checked-in venue report source. `raw/`, `interim/` and `processed/` hold generated or separately restored archives, scorecard records, feature tables and fantasy histories. Contents can be large and may be absent from a source-only checkout.

The API and sync command resolve this root via `NEW_X1_DATA_ROOT` or [`project_paths.py`](../project_paths.py); avoid mixing snapshots from different checkouts. Keep dated source data and manifests for reproducibility. See the [active processing guide](../data_processing/README.md) and [runbook](../docs/RUNBOOK.md). Data-only generated subfolders do not need source READMEs.
