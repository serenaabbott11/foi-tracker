"""Auth: add the `users` table.

Idempotent — uses `CREATE TABLE IF NOT EXISTS`. Safe to run against an
existing DB.

Schema:
    id             INTEGER PK
    username       TEXT UNIQUE NOT NULL
    password_hash  TEXT NOT NULL           werkzeug.security hash
    role           TEXT NOT NULL DEFAULT 'caseworker'
                                            'admin' | 'foi_officer' | 'caseworker'
    team_id        TEXT                    (populated when DP-4 lands)
    created_at     TEXT NOT NULL           ISO-8601 UTC
    updated_at     TEXT

Usage:
    python -m scripts.migrate_add_users
    python -m scripts.migrate_add_users --db /path/to/foi.db
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = str(ROOT / "data" / "foi.db")

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT 'caseworker',
    team_id        TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
"""


def apply(conn: sqlite3.Connection) -> None:
    """Apply the users schema to conn. Idempotent."""
    conn.executescript(USERS_SCHEMA)
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add the users table.")
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
    print(f"Applied users schema to {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
