# Optional cloud permissions

[`iam-reader.json`](iam-reader.json) and [`iam-writer.json`](iam-writer.json) are policy examples for the optional private release object store. The current Cloudflare Pages/laptop deployment does not create or require an AWS bucket. Review and scope any future bucket/region/resource ARNs before applying these policies; credentials belong in a secret store, never here.

The implementation they support lives in [`pipeline/`](../pipeline/README.md). The active hosting process is described in the [Cloudflare guide](../docs/CLOUDFLARE_DEMO.md). No live cloud-permission check was performed by the local test suite.
