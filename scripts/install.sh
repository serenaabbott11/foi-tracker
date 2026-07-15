#!/usr/bin/env bash
# OPS-4b: install the FOI Deadline Tracker as a systemd service.
#
# Idempotent — safe to re-run for upgrades. Creates the service user,
# /opt/foi-tracker (code), /var/lib/foi-tracker (data + backups),
# /var/log/foi-tracker (logs), a venv, installs systemd units, starts
# them. Generates a SECRET_KEY on first run.
#
# Must be run as root (sudo). Assumes Debian/Ubuntu with systemd.
#
# Environment (override as needed):
#   SERVICE_USER   service account       (default: foi-tracker)
#   INSTALL_DIR    code goes here        (default: /opt/foi-tracker)
#   DATA_DIR       DB + backups          (default: /var/lib/foi-tracker)
#   LOG_DIR        gunicorn access/error (default: /var/log/foi-tracker)
#   ENV_FILE       systemd EnvironmentFile (default: /etc/foi-tracker/env)

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "error: install.sh must be run as root (sudo)" >&2
    exit 1
fi

for cmd in rsync python3 systemctl; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        echo "error: missing required command: $cmd" >&2
        exit 1
    fi
done

SERVICE_USER="${SERVICE_USER:-foi-tracker}"
INSTALL_DIR="${INSTALL_DIR:-/opt/foi-tracker}"
DATA_DIR="${DATA_DIR:-/var/lib/foi-tracker}"
LOG_DIR="${LOG_DIR:-/var/log/foi-tracker}"
BACKUP_DIR="${BACKUP_DIR:-$DATA_DIR/backups}"
ENV_FILE="${ENV_FILE:-/etc/foi-tracker/env}"

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== FOI Deadline Tracker installer =="
echo "  source:   $SRC_DIR"
echo "  install:  $INSTALL_DIR"
echo "  data:     $DATA_DIR"
echo "  log:      $LOG_DIR"
echo "  env:      $ENV_FILE"
echo

# 1. Service user
if ! id -u "$SERVICE_USER" > /dev/null 2>&1; then
    useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "created service user: $SERVICE_USER"
fi

# 2. Directories
mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR" "$BACKUP_DIR" "$(dirname "$ENV_FILE")"

# 3. Copy code (excluding local dev artefacts)
rsync -a --delete \
    --exclude __pycache__ --exclude '*.pyc' \
    --exclude data/ --exclude backups/ \
    --exclude .git/ --exclude .venv/ --exclude venv/ \
    --exclude 'plan.md' --exclude '.env' \
    "$SRC_DIR/" "$INSTALL_DIR/"

# 4. venv + deps (recreated to guarantee a clean install of gunicorn)
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# 5. Env file — generated on first install only.
if [[ ! -f "$ENV_FILE" ]]; then
    SECRET_KEY_VAL="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    cat > "$ENV_FILE" <<EOF
# FOI Deadline Tracker — read by systemd EnvironmentFile.
SECRET_KEY=$SECRET_KEY_VAL
FOI_DB=$DATA_DIR/foi.db
BACKUP_DIR=$BACKUP_DIR
EOF
    chmod 600 "$ENV_FILE"
    echo "created env file: $ENV_FILE (fresh SECRET_KEY generated)"
fi

# 6. First-run seed or upgrade migrations.
# shellcheck disable=SC1090
if [[ ! -f "$DATA_DIR/foi.db" ]]; then
    (set -a; source "$ENV_FILE"; \
        cd "$INSTALL_DIR" && "$INSTALL_DIR/.venv/bin/python" -m scripts.seed)
    echo "seeded fresh DB at $DATA_DIR/foi.db"
else
    (set -a; source "$ENV_FILE"; \
        cd "$INSTALL_DIR" && \
        "$INSTALL_DIR/.venv/bin/python" -m scripts.migrate_add_audit_log && \
        "$INSTALL_DIR/.venv/bin/python" -m scripts.migrate_add_retention)
    echo "existing DB migrated in place"
fi

# 7. Ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$ENV_FILE"

# 8. Install systemd units
install -m 644 "$SRC_DIR/deploy/systemd/foi-tracker.service"        /etc/systemd/system/
install -m 644 "$SRC_DIR/deploy/systemd/foi-tracker-backup.service" /etc/systemd/system/
install -m 644 "$SRC_DIR/deploy/systemd/foi-tracker-backup.timer"   /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now foi-tracker.service
systemctl enable --now foi-tracker-backup.timer

echo
echo "== install complete =="
echo "  app service:     $(systemctl is-active foi-tracker.service)"
echo "  backup timer:    $(systemctl is-active foi-tracker-backup.timer)"
echo "  next backup:     $(systemctl list-timers foi-tracker-backup.timer --no-pager --no-legend | awk '{print $1, $2, $3, $4}')"
echo
echo "  check health with:  curl http://127.0.0.1:5002/api/healthz"
echo "  view logs with:     journalctl -u foi-tracker.service -f"
