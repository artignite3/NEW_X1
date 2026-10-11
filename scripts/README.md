# Operator scripts

[`smoke_local.py`](smoke_local.py) loads a trusted artifact checkout and exercises model loading, fixture generation, independent validation and explanation using isolated local test authentication. For example, run `python scripts/smoke_local.py --artifacts-root '<absolute artifact checkout>'` from the root. It does not test Supabase or the public tunnel.

[`start_cloudflare_demo.ps1`](start_cloudflare_demo.ps1) is a PowerShell helper for the local API/tunnel demo. The preferred one-step launcher at repository root is [`run_all.bat`](../run_all.bat), which calls [`run_all.py`](../run_all.py), verifies all saved models, and announces a public URL only after a remote health check.

[`check_docs.py`](check_docs.py) validates local Markdown links with `python scripts/check_docs.py`; add `--include-archive` for dated notes. Run operator scripts from the repository root with a restored artifact checkout. The tunnel requires `cloudflared` or the documented localhost.run fallback and working outbound DNS/network access; provider refresh is separate. Test launcher behavior with `python -m unittest tests.test_run_all -v`. See the [runbook](../docs/RUNBOOK.md) and [Cloudflare guide](../docs/CLOUDFLARE_DEMO.md).
