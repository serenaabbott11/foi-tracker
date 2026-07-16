#!/usr/bin/env python3
"""Create a consistent, verified backup of the FOI database.

Uses SQLite's online backup API, so it is safe to run *while the app is
serving traffic* — no need to stop the service or lock the file, and the
snapshot is transactionally consistent (no half-written rows).

    python -m scripts.backup                 # back up the default DB
    FOI_DB=/path/to.db python -m scripts.backup

Backups land in data/backups/ (override with FOI_BACKUP_DIR) as
    foi-YYYYMMDD-HHMMSS.db
The newest FOI_BACKUP_KEEP (default 14) are retained; older ones are pruned.
Every backup is verified with PRAGMA integrity_check before it counts.
"""
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foi_tracker.config import BACKUP_DIR, DB_PATH

KEEP = int(os.environ.get("FOI_BACKUP_KEEP", "14"))


def _integrity_ok(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def make_backup(db_path=DB_PATH, backup_dir=BACKUP_DIR):
    """Snapshot db_path into backup_dir; return the backup's Path."""
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"No database at {db_path} — nothing to back up")
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"foi-{stamp}.db"

    # Read-only source + online backup = consistent even under concurrent writes.
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    result = _integrity_ok(dest)
    if result != "ok":
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"Backup failed integrity check: {result}")

    return dest


def prune(backup_dir=BACKUP_DIR, keep=KEEP):
    """Delete all but the newest `keep` backups; return the pruned list."""
    backups = sorted(Path(backup_dir).glob("foi-*.db"))
    stale = backups[:-keep] if keep > 0 else []
    for old in stale:
        old.unlink()
    return stale


def main():
    dest = make_backup()
    pruned = prune()
    print(f"Backup OK: {dest} ({dest.stat().st_size} bytes, integrity_check=ok)")
    if pruned:
        print(f"Pruned {len(pruned)} old backup(s), keeping newest {KEEP}")


if __name__ == "__main__":
    main()
