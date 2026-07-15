#!/usr/bin/env python3
"""Restore the FOI database from a backup.

    python -m scripts.restore                          # newest backup
    python -m scripts.restore data/backups/foi-20260715-140000.db

Before overwriting, the current live DB (if any) is copied aside to
    <db>.pre-restore-YYYYMMDD-HHMMSS
so the restore is itself reversible. The backup is integrity-checked first;
a corrupt backup is refused rather than written over good-ish data.
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foi_tracker.config import BACKUP_DIR, DB_PATH, ensure_dirs


def latest_backup(backup_dir=BACKUP_DIR):
    backups = sorted(Path(backup_dir).glob("foi-*.db"))
    if not backups:
        raise FileNotFoundError(f"No backups found in {backup_dir}")
    return backups[-1]


def _integrity_ok(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def restore(backup_path=None, db_path=DB_PATH):
    """Restore db_path from backup_path (newest if None).

    Returns (backup_used, safety_copy_or_None).
    """
    db_path = Path(db_path)
    backup_path = Path(backup_path) if backup_path else latest_backup()
    if not backup_path.exists():
        raise FileNotFoundError(backup_path)

    result = _integrity_ok(backup_path)
    if result != "ok":
        raise RuntimeError(f"Refusing to restore corrupt backup: {result}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    safety = None
    if db_path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safety = db_path.with_name(f"{db_path.name}.pre-restore-{stamp}")
        shutil.copy2(db_path, safety)

    shutil.copy2(backup_path, db_path)
    return backup_path, safety


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    ensure_dirs()
    src, safety = restore(arg)
    print(f"Restored {DB_PATH} from {src}")
    if safety:
        print(f"Previous DB preserved at {safety}")


if __name__ == "__main__":
    main()
