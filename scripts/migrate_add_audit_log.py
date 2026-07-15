"""AUD-1: add the audit_log table and its immutability triggers.

Idempotent — safe to run against an existing DB. Creates the table, its
indexes, and the BEFORE UPDATE / BEFORE DELETE triggers if they don't
already exist.

Usage:
    python -m scripts.migrate_add_audit_log
    python -m scripts.migrate_add_audit_log --db /path/to/foi.db
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = str(ROOT / "data" / "foi.db")


AUDIT_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    actor        TEXT NOT NULL,
    actor_ip     TEXT,
    action       TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT,
    before_json  TEXT,
    after_json   TEXT,
    reason       TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity
    ON audit_log (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
    ON audit_log (timestamp);

CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit log is immutable');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit log is immutable');
END;
"""


def apply(conn: sqlite3.Connection) -> None:
    """Apply the audit_log schema to conn. Idempotent."""
    conn.executescript(AUDIT_LOG_SCHEMA)
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add audit_log table + triggers.")
    parser.add_argument(
        "--db",
        default=os.environ.get("FOI_DB", DEFAULT_DB_PATH),
        help="path to the SQLite DB (default: $FOI_DB or <repo>/data/foi.db)",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(
            f"error: {args.db} does not exist. Run scripts.seed first.",
            file=sys.stderr,
        )
        return 1

    conn = sqlite3.connect(args.db)
    apply(conn)
    conn.close()
    print(f"Applied audit_log schema to {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
