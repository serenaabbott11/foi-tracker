"""DP-1: add UK GDPR retention columns to the `requests` table.

Idempotent — uses PRAGMA table_info to check which columns already exist
before adding them. Safe to run against an existing DB.

Columns added:
    created_at        TEXT  ISO-8601 UTC — when the row was first inserted
    updated_at        TEXT  ISO-8601 UTC — last mutation
    responded_at      TEXT  ISO-8601 UTC — set on transition to 'Responded'
    retention_until   TEXT  ISO-8601 date — when PII is due for erasure (set
                            by the DP-3 retention sweeper)
    team_id           TEXT  for multi-directorate separation (DP-4)

Backfill for existing rows:
    created_at   <- received   (best proxy we have)
    updated_at   <- received
    responded_at <- received   IF status = 'Responded' ELSE NULL
    retention_until, team_id   NULL — filled in when DP-3 / DP-4 land

Usage:
    python -m scripts.migrate_add_retention
    python -m scripts.migrate_add_retention --db /path/to/foi.db
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = str(ROOT / "data" / "foi.db")

_NEW_COLUMNS = [
    ("created_at", "TEXT"),
    ("updated_at", "TEXT"),
    ("responded_at", "TEXT"),
    ("retention_until", "TEXT"),
    ("team_id", "TEXT"),
]


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply(conn: sqlite3.Connection) -> None:
    """Add retention columns to `requests` and backfill. Idempotent."""
    existing = _existing_columns(conn, "requests")
    if not existing:
        raise RuntimeError(
            "requests table not found — run scripts.seed first, or the "
            "audit_log migration cannot proceed without a base schema."
        )

    added: list[str] = []
    for name, coltype in _NEW_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE requests ADD COLUMN {name} {coltype}")
            added.append(name)

    # Backfill only rows where the columns are NULL — safe on re-runs.
    # created_at / updated_at fall back to `received`; responded_at only
    # when status is 'Responded'.
    conn.execute(
        "UPDATE requests SET created_at = received WHERE created_at IS NULL"
    )
    conn.execute(
        "UPDATE requests SET updated_at = received WHERE updated_at IS NULL"
    )
    conn.execute(
        "UPDATE requests SET responded_at = received "
        "WHERE responded_at IS NULL AND status = 'Responded'"
    )
    conn.commit()

    return added  # useful for tests / logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add DP-1 retention columns.")
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
    added = apply(conn)
    conn.close()
    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("Retention columns already present — nothing to do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
