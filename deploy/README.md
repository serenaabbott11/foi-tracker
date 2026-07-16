# `deploy/`

Deployment artefacts for the FOI Deadline Tracker.

| Path | What | Status |
|---|---|---|
| [`systemd/`](systemd/) | systemd service + backup timer for `scripts/install.sh` | **Real** — used by `install.sh`, tested statically |
| [`k8s/`](k8s/) | Kubernetes manifests | **⚠️ Aspirational — not deployed** |
| [`terraform/`](terraform/) | Terraform module for AWS | **⚠️ Aspirational — not applied** |

The aspirational files exist so we can talk credibly about the direction of
travel in the ICO audit and the Day 2 presentation. They have **not** been
applied to a real cluster or cloud account. Each has a disclaimer at the top
of its own README.

See [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) for the real deployment
paths (Docker Compose, systemd on a single VM).
