"""Create a user in the FOI Deadline Tracker.

For real (non-demo) users. Prompts for the password interactively so it never
lands in shell history.

Usage:
    python -m scripts.create_user --username jane
    python -m scripts.create_user --username jane --role admin
    python -m scripts.create_user --username jane --team-id central-foi

Roles: admin | foi_officer | caseworker  (default: caseworker)
"""
import argparse
import getpass
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foi_tracker.audit import now_utc_iso  # noqa: E402
from foi_tracker.auth import hash_password  # noqa: E402

DEFAULT_DB_PATH = str(ROOT / "data" / "foi.db")
ROLES = ("admin", "foi_officer", "caseworker")


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    role: str = "caseworker",
    team_id: str | None = None,
) -> int:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    if not username or not password:
        raise ValueError("username and password are required")

    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, team_id, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (username, hash_password(password), role, team_id, now_utc_iso()),
    )
    conn.commit()
    return cur.lastrowid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a FOI Tracker user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", default="caseworker", choices=ROLES)
    parser.add_argument("--team-id", default=None, dest="team_id")
    parser.add_argument(
        "--db",
        default=os.environ.get("FOI_DB", DEFAULT_DB_PATH),
        help="path to the SQLite DB (default: $FOI_DB or <repo>/data/foi.db)",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"error: {args.db} does not exist. Run scripts.seed first.", file=sys.stderr)
        return 1

    password = getpass.getpass(f"Password for {args.username}: ")
    if not password:
        print("error: password cannot be empty", file=sys.stderr)
        return 1
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("error: passwords do not match", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    try:
        user_id = create_user(
            conn,
            username=args.username,
            password=password,
            role=args.role,
            team_id=args.team_id,
        )
    except sqlite3.IntegrityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f"Created user id={user_id} username={args.username} role={args.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
