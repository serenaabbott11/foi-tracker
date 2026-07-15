#!/usr/bin/env bash
# OPS-3: restore the FOI Deadline Tracker DB from a backup file.
#
# Usage: scripts/restore.sh <backup-file.db.gz>
#
# 1. Extract the backup to a staging path (same filesystem as target).
# 2. Smoke test — must have `requests` and `audit_log` tables and be readable.
# 3. Move the current live DB aside as a safety copy (if it exists).
# 4. Move the staging DB into the live path (atomic on same fs).
# 5. Log the restore to audit_log on the newly-restored DB.
#
# Env vars:
#   FOI_DB   Path to the target DB   (default: <repo>/data/foi.db)

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <backup-file.db.gz>" >&2
    exit 2
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "error: backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FOI_DB="${FOI_DB:-$REPO_ROOT/data/foi.db}"
TARGET_DIR="$(dirname "$FOI_DB")"
mkdir -p "$TARGET_DIR"

STAGE="$(mktemp "$TARGET_DIR/.restore-staging.XXXXXX.db")"
trap 'rm -f "$STAGE"' EXIT

# 1. Extract
gunzip -c "$BACKUP_FILE" > "$STAGE"

# 2. Smoke test — required tables + readable
if ! sqlite3 "$STAGE" "SELECT count(*) FROM requests;" > /dev/null 2>&1; then
    echo "error: staging DB failed smoke test (requests table missing / unreadable)" >&2
    exit 1
fi
if ! sqlite3 "$STAGE" "SELECT count(*) FROM audit_log;" > /dev/null 2>&1; then
    echo "error: staging DB failed smoke test (audit_log table missing / unreadable)" >&2
    exit 1
fi

REQ_COUNT="$(sqlite3 "$STAGE" 'SELECT count(*) FROM requests;')"
echo "smoke test ok: $REQ_COUNT rows in requests"

# 3. Move current live DB aside
if [[ -f "$FOI_DB" ]]; then
    SAFETY="$FOI_DB.pre-restore-$(date -u +%Y%m%d-%H%M%SZ)"
    mv "$FOI_DB" "$SAFETY"
    echo "existing DB moved aside: $SAFETY"
fi

# 4. Swap in
mv "$STAGE" "$FOI_DB"
trap - EXIT
echo "restored $BACKUP_FILE -> $FOI_DB"

# 5. Audit log the restore itself. Best-effort — restore already succeeded.
NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sqlite3 "$FOI_DB" <<SQL || echo "warning: audit_log write failed (restore itself is complete)" >&2
INSERT INTO audit_log
  (timestamp, actor, action, entity_type, entity_id, reason)
VALUES
  ('$NOW_UTC', 'system', 'restore', 'backup', NULL, '$BACKUP_FILE');
SQL
