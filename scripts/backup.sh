#!/usr/bin/env bash
# OPS-3: snapshot and compress the FOI Deadline Tracker SQLite DB.
#
# Uses SQLite's online backup API (`sqlite3 .backup`) so it is safe even
# when the DB is being written to. Produces a timestamped gzipped file
# in $BACKUP_DIR and prunes older ones (last 14 kept). Writes an
# `action='backup'` row to audit_log.
#
# Env vars:
#   FOI_DB      Path to source DB    (default: <repo>/data/foi.db)
#   BACKUP_DIR  Where backups go     (default: <repo>/backups)
#
# Exits non-zero on any failure so cron / systemd timers notice.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FOI_DB="${FOI_DB:-$REPO_ROOT/data/foi.db}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"

if [[ ! -f "$FOI_DB" ]]; then
    echo "error: source DB not found: $FOI_DB" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date -u +%Y%m%d-%H%M%SZ)"
# Stage on the same filesystem as the backup dir so the final mv is atomic.
STAGE="$(mktemp "$BACKUP_DIR/.staging.XXXXXX.db")"
FINAL="$BACKUP_DIR/foi-$TIMESTAMP.db.gz"

sqlite3 "$FOI_DB" ".backup '$STAGE'"
gzip -c "$STAGE" > "$FINAL"
rm -f "$STAGE"

# Retention: keep the 14 most recent .db.gz files.
# Weekly retention is a manual promotion step documented in
# docs/RESTORE-DRILL.md.
find "$BACKUP_DIR" -maxdepth 1 -name 'foi-*.db.gz' -printf '%T@ %p\n' \
    | sort -rn \
    | awk 'NR>14 {print $2}' \
    | xargs -r rm -f

# Audit — best-effort. A missing audit_log table shouldn't fail the
# backup (the backup already succeeded).
NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sqlite3 "$FOI_DB" <<SQL || echo "warning: audit_log write failed (backup itself is complete)" >&2
INSERT INTO audit_log
  (timestamp, actor, action, entity_type, entity_id, reason)
VALUES
  ('$NOW_UTC', 'system', 'backup', 'backup', NULL, '$FINAL');
SQL

echo "Backup complete: $FINAL"
