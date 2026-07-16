# `deploy/`

Deployment artefacts for the FOI Deadline Tracker.

| Path | What |
|---|---|
| [`systemd/`](systemd/) | systemd service + backup timer for `scripts/install.sh` — the real deployment shape |

See [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) for the full deployment
story (Docker Compose in dev, systemd on a single VM in production).
