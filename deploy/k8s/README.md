# Kubernetes manifests — **aspirational**

> ⚠️ **This is a demonstrative artefact.** It has **not** been applied to a
> real cluster. Do **not** deploy to production without a DPIA update,
> departmental approval, and the additions listed under §"What's missing"
> below.

## Why this exists

The ICO audit will want to see we've thought about "what happens as the
service grows." These manifests describe what a minimal Kubernetes
deployment would look like for the FOI Deadline Tracker, using the same
container image the `Dockerfile` produces.

They are **not** the recommended production shape. See the "why not" section
at the bottom.

## What's here

| File | Kind | Purpose |
|---|---|---|
| `deployment.yaml` | Deployment | 1 replica (SQLite is not multi-writer), non-root, readiness + liveness probes on `/api/healthz` |
| `service.yaml` | Service | ClusterIP :80 → :5002 |
| `configmap.yaml` | ConfigMap | Non-secret env: `FOI_DB`, `BACKUP_DIR`, `LOG_LEVEL`, `LOG_DIR` |
| `secret.yaml.example` | Secret | **Placeholder**. Do not commit real secrets. See file header for how to generate |
| `pvc.yaml` | PersistentVolumeClaim | 1 GiB for `/data`. `ReadWriteOnce` — matches the single-replica constraint |

## What's missing (i.e. what a real deployment would still need)

- **Ingress + TLS** (nginx-ingress / traefik / a cloud LB, plus cert-manager).
- **Secret management** — the example is a plain K8s `Secret`. Real deployments should use sealed-secrets, external-secrets pointing at a KMS, or Vault.
- **Backup CronJob** — the systemd path uses a `foi-tracker-backup.timer`; the K8s equivalent is a `CronJob` that `kubectl exec`s or runs the same `backup.sh` in a sidecar. Not included.
- **Monitoring / alerting** — no ServiceMonitor / PodMonitor.
- **NetworkPolicy** — namespace default is "open"; needs restriction.
- **Resource limits / requests** — placeholders below are conservative; needs a load test to be real.
- **PodDisruptionBudget** — single-replica so trivially "1 unavailable" but should be explicit.

## Why we would *not* pick K8s for this workload today

- 6 caseworkers, moving to ~20. K8s brings ~15 new operational surfaces (kubelet, control plane, ingress, cert-manager, RBAC, secrets store, monitoring, upgrades) — each one is a thing the ICO audit will want to see managed.
- SQLite is single-writer. Any multi-replica story requires either accepting downtime for restarts (`strategy: Recreate`, which we do below) or migrating to a managed DB — a separate DPIA-sized decision.
- The GDS Way explicitly cautions against over-scaling infrastructure to what the workload actually needs.

If the service grew to serve every DfT directorate and 50+ concurrent users,
this becomes worth revisiting. Until then, the systemd path in
`../systemd/` (single VM) is the honest deployment story.
