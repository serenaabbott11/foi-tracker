# Terraform — **aspirational**

> ⚠️ **This module has never been `terraform apply`d.** No state file exists,
> no cloud account is referenced. Do **not** use in production without a
> DPIA update, the departmental cloud landing zone, secrets management, and
> the additions listed under §"What's missing" below.

## Why this exists

Same reason as the K8s manifests: to describe the direction of travel for
the ICO audit. This module is the smallest reasonable AWS deployment of a
single-VM Flask app with SQLite. It is **not** a production template.

## What this provisions (sketch)

| Resource | Purpose |
|---|---|
| VPC (default), subnet, security group | Network |
| EC2 instance (t3.small) | Runs the same Docker image via `docker compose` |
| EBS volume (gp3, 10 GiB) | Mounted at `/data` for the SQLite DB |
| S3 bucket + versioning + lifecycle | Off-site backups (`backup.sh` uploads to this) |
| Route 53 A record | Friendly DNS name |
| IAM role + instance profile | EC2 → S3 backup bucket write; nothing else |
| CloudWatch log group | App logs from Docker |

## What's missing (i.e. what a real deployment would need)

- **A landing zone.** Departmental cloud accounts have baseline controls
  (SCPs, guardrails, tag policies) that this bare module doesn't respect.
- **TLS.** No ACM certificate, no HTTPS listener. Real deployment needs an
  ALB + ACM cert.
- **Secrets management.** SECRET_KEY should come from Systems Manager
  Parameter Store or Secrets Manager, not user-data.
- **Backup off-site.** S3 versioning is included, but object-lock (WORM),
  cross-region replication, and lifecycle to Glacier are not.
- **Access controls.** SSH is via SSM Session Manager — not shown here.
  IAM policies should be more granular than the sketch.
- **Monitoring / alerting.** CloudWatch metric alarms not defined.
- **Cost.** t3.small + EBS + a tiny S3 bucket is ~$20/month at us-east-1
  list prices. Real DPIA needs to justify this.

## Why we would still resist Terraform-ing this today

- We don't have a cloud target with approvals.
- The single-VM systemd path (see `../systemd/`) meets the workload's real
  needs (6–20 users) without a cloud dependency.
- Adding cloud infrastructure moves PII off-premise — that's a DPIA update
  the department has to sign off, not something a hackathon commits us to.

If the department decides to move this to AWS, this module is the starting
point — but it needs the "what's missing" list above closed first.
