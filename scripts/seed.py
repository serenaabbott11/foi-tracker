"""Create foi.db and load sample requests.

Run from the repo root:

    python -m scripts.seed              # refuses if the DB already exists
    python -m scripts.seed --force      # overwrite an existing DB
    python -m scripts.seed --db /tmp/x  # target a specific path

Honours FOI_DB from the environment as the default target path.
"""
import argparse
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foi_tracker.deadlines import calculate_deadline  # noqa: E402
from scripts.migrate_add_audit_log import apply as apply_audit_log  # noqa: E402

DEFAULT_DB_PATH = str(ROOT / "data" / "foi.db")

SAMPLE = [
    ("FOI-2026-0141", "J. Whitfield", "Pothole repair spend by borough, 2024-2026", 38, "Responded"),
    ("FOI-2026-0152", "Roadside Truths blog", "Smart motorway incident response times", 31, "Responded"),
    ("FOI-2026-0159", "M. Osei", "Rail electrification feasibility studies since 2020", 27, "Internal review"),
    ("FOI-2026-0163", "Kent Online", "Correspondence about the Lower Thames Crossing", 24, "In progress"),
    ("FOI-2026-0170", "S. Brar", "EV charging point grant applications rejected in 2025", 19, "In progress"),
    ("FOI-2026-0174", "Cycling UK", "Active travel budget reallocations", 16, "In progress"),
    ("FOI-2026-0178", "P. Lindqvist", "Ministerial meetings with airline lobbyists", 12, "In progress"),
    ("FOI-2026-0181", "Transport Action Group", "Bus service improvement plan funding formula", 9, "Received"),
    ("FOI-2026-0183", "A. Ncube", "Driving test backlog by test centre", 6, "Received"),
    ("FOI-2026-0185", "The Herald", "Costs of the pavement parking consultation", 3, "Received"),
    ("FOI-2026-0186", "R. Kaminski", "Departmental spend on taxis, 2025", 1, "Received"),
    ("FOI-2026-0187", "L. Fortescue", "Bridge inspection reports for the A38", 0, "Received"),
    ("FOI-2026-0188", "N. Ahmed", "Rural road resurfacing programme, 2026-27", -36, "Received"),
]


def seed(db_path: str, force: bool = False) -> None:
    """Create the schema and insert sample rows at db_path.

    Refuses to touch an existing file unless force=True. Creates the
    parent directory if it does not exist.
    """
    if os.path.exists(db_path):
        if not force:
            raise SystemExit(
                f"error: {db_path} already exists. Pass --force to overwrite."
            )
        os.remove(db_path)

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref TEXT,
            requester TEXT,
            subject TEXT,
            received TEXT,
            deadline TEXT,
            status TEXT,
            notes TEXT
        )
        """
    )
    for ref, requester, subject, days_ago, status in SAMPLE:
        received = date.today() - timedelta(days=days_ago)
        deadline = calculate_deadline(received)
        conn.execute(
            "INSERT INTO requests (ref, requester, subject, received, deadline, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, '')",
            (ref, requester, subject, received.isoformat(), deadline.isoformat(), status),
        )
    apply_audit_log(conn)
    conn.commit()
    conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed foi.db with sample requests.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite the existing DB if present",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("FOI_DB", DEFAULT_DB_PATH),
        help="path to the SQLite DB (default: $FOI_DB or <repo>/data/foi.db)",
    )
    args = parser.parse_args(argv)
    seed(args.db, force=args.force)
    print(f"Seeded {args.db} with {len(SAMPLE)} requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
