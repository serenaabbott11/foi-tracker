# Deployment

Two supported paths, matching the brief:

- **A. Docker** (`Dockerfile` + `docker-compose.yml`) — for anywhere that has Docker.
- **B. systemd** (`scripts/install.sh` + `deploy/systemd/*.unit`) — for a bare Linux host.

Both use the same code, the same env vars, and the same backup / restore scripts. Both run under a non-root user and expose `/api/healthz` for external monitoring.

---

## Path A — Docker

**Prerequisites:** Docker Engine and Docker Compose v2.

```bash
# 1. One-time: generate a real SECRET_KEY and stash it in .env.
cp .env.example .env
sed -i "s/CHANGE_ME/$(python3 -c 'import secrets; print(secrets.token_hex(32))')/" .env

# 2. Build and start.
docker compose up -d --build

# 3. First-time seed (creates schema + sample data + audit_log + retention cols).
docker compose exec app python -m scripts.seed --force

# 4. Verify.
curl http://localhost:5002/api/healthz    # -> {"ok":true,"db":true}
```

**Manual backup:** `docker compose exec app python -m scripts.backup` — writes into `data/backups/`. To pull backups out to the host:

```bash
docker compose cp app:/app/data/backups ./backups-export/
```

**Restore:** copy a `.db` back into the container, then run the restore script:

```bash
docker compose cp ./backups-export/foi-20260715-020000.db app:/app/data/backups/
docker compose exec app python -m scripts.restore /app/data/backups/foi-20260715-020000.db
```

**Automating backups under Docker:** the `foi-tracker-backup.timer` systemd unit is not applicable here. Use a host-side cron entry:

```cron
0 2 * * *  docker compose --project-directory /opt/foi-tracker exec -T app python -m scripts.backup
```

---

## Path B — systemd

**Prerequisites:** Debian / Ubuntu host with `python3`, `rsync`, `sqlite3`, and systemd.

```bash
sudo ./scripts/install.sh
```

That's the whole install. On first run the script:

1. Creates the `foi-tracker` service user.
2. Lays out `/opt/foi-tracker` (code), `/var/lib/foi-tracker` (DB + backups), `/var/log/foi-tracker`.
3. Builds a Python venv and installs deps (including Gunicorn).
4. Generates `SECRET_KEY` and writes `/etc/foi-tracker/env` (`chmod 600`).
5. Seeds a fresh DB (or migrates an existing one on re-run).
6. Installs and starts `foi-tracker.service` + `foi-tracker-backup.timer`.

**Verify:**

```bash
systemctl is-active foi-tracker.service     # active
systemctl is-active foi-tracker-backup.timer # active
systemctl list-timers foi-tracker-backup    # next fire time
curl http://127.0.0.1:5002/api/healthz      # {"ok":true,"db":true}
```

**Upgrades:** re-run `sudo ./scripts/install.sh`. The rsync pushes new code, the venv is recreated, and the DB migrations (idempotent) are applied without touching data.

**Logs:**

- App (Gunicorn): `journalctl -u foi-tracker.service -f`
- Access / error files: `/var/log/foi-tracker/access.log`, `error.log`
- Backup timer: `journalctl -u foi-tracker-backup.timer -f`

**Reverse proxy:** the service binds to `127.0.0.1:5002`. Put nginx / Apache / caddy in front for TLS + hostname routing. (Not covered here — depends on your host's HTTPS story.)

---

## Health and observability

- `GET /api/healthz` returns `200 {"ok": true, "db": true}` when the app *and* the DB are up; `503` otherwise. Cheap, auth-free, safe to hammer.
- Every audit-relevant action writes a row to `audit_log` (see `plan.md` §AUD and `foi_tracker/audit.py`).
- Backups and restores also write `audit_log` rows.

## Restore

The restore drill is documented separately in [`docs/RESTORE-DRILL.md`](RESTORE-DRILL.md). Rehearse it before you need it.

## Not doing (and why)

- **No cloud deployment** — no budget, no clearance to move the PII off-premise, no DPIA update.
- **No HA / clustering** — 6–20 users; one node with a tested restore beats two nodes with untested backups.
- **No Kubernetes / Terraform** — the app is a single-VM systemd deployment. SQLite is single-writer, so multi-replica orchestration would be theatre without a database swap.
