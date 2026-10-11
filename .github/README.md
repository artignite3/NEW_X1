# GitHub automation

[`workflows/`](workflows/README.md) contains the repository's verification and static-site deployment workflows. The code checkout can pass local tests without proving these jobs passed on GitHub; inspect each run before release. Deployment variables and tokens live in GitHub Actions settings, never in workflow files.

See the [Cloudflare guide](../docs/CLOUDFLARE_DEMO.md) and [audit](../docs/audit/README.md).
