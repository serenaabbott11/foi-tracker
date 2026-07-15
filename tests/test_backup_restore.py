"""OPS-3: end-to-end test for scripts/backup.sh and scripts/restore.sh.

Uses subprocess to invoke the bash scripts against a temp DB, then verifies
the backup exists, contains the expected data, and that restore round-trips.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUP_SH = REPO_ROOT / "scripts" / "backup.sh"
RESTORE_SH = REPO_ROOT / "scripts" / "restore.sh"


def _seed_temp_db(db_path: str) -> None:
    """Populate a temp DB with the minimum schema + one row + audit_log."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref TEXT, requester TEXT, subject TEXT,
            received TEXT, deadline TEXT, status TEXT, notes TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO requests (ref, requester, subject, received, deadline, status, notes) "
        "VALUES ('FOI-BAK-1', 'A. Tester', 'backup test', "
        "'2026-01-01', '2026-01-29', 'Received', '')"
    )
    from scripts.migrate_add_audit_log import apply as apply_audit_log
    from scripts.migrate_add_retention import apply as apply_retention

    apply_audit_log(conn)
    apply_retention(conn)
    conn.commit()
    conn.close()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Isolated FOI_DB + BACKUP_DIR under tmp_path."""
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    db_path = data_dir / "foi.db"
    _seed_temp_db(str(db_path))

    monkeypatch.setenv("FOI_DB", str(db_path))
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))

    yield {"db": db_path, "backups": backup_dir, "root": tmp_path}


def _run(script: Path, *args, env=None):
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def test_backup_creates_gz_file(workspace):
    result = _run(BACKUP_SH)
    assert result.returncode == 0, result.stderr

    gz_files = list(workspace["backups"].glob("foi-*.db.gz"))
    assert len(gz_files) == 1
    assert gz_files[0].stat().st_size > 0


def test_backup_writes_audit_row(workspace):
    _run(BACKUP_SH)

    conn = sqlite3.connect(str(workspace["db"]))
    rows = conn.execute(
        "SELECT action, actor, reason FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "backup"
    assert rows[0][1] == "system"
    assert ".db.gz" in rows[0][2]


def test_restore_round_trip(workspace):
    # Baseline: how many rows should we see after restore?
    conn = sqlite3.connect(str(workspace["db"]))
    baseline_count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    conn.close()

    _run(BACKUP_SH)

    # Simulate disaster.
    workspace["db"].unlink()
    assert not workspace["db"].exists()

    backup_files = sorted(workspace["backups"].glob("foi-*.db.gz"))
    assert backup_files, "no backup to restore from"
    result = _run(RESTORE_SH, str(backup_files[-1]))
    assert result.returncode == 0, result.stderr
    assert "smoke test ok" in result.stdout

    # DB is back with the pre-disaster row count.
    assert workspace["db"].exists()
    conn = sqlite3.connect(str(workspace["db"]))
    count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    conn.close()
    assert count == baseline_count


def test_restore_writes_audit_row(workspace):
    _run(BACKUP_SH)
    workspace["db"].unlink()

    backup_files = sorted(workspace["backups"].glob("foi-*.db.gz"))
    _run(RESTORE_SH, str(backup_files[-1]))

    conn = sqlite3.connect(str(workspace["db"]))
    row = conn.execute(
        "SELECT action, actor, reason FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "restore"
    assert row[1] == "system"
    assert ".db.gz" in row[2]


def test_restore_refuses_corrupt_backup(workspace, tmp_path):
    """A backup file that doesn't decompress to a valid DB must be rejected."""
    bad_gz = tmp_path / "not-really-a-backup.db.gz"
    # Write a gzipped file whose contents aren't a SQLite DB.
    import gzip

    with gzip.open(bad_gz, "wb") as f:
        f.write(b"this is not a sqlite database")

    result = _run(RESTORE_SH, str(bad_gz))
    assert result.returncode != 0
    assert "smoke test" in result.stderr or "failed" in result.stderr.lower()
    # The live DB should be untouched.
    assert workspace["db"].exists()


def test_restore_missing_file_errors(workspace):
    result = _run(RESTORE_SH, "/no/such/file.db.gz")
    assert result.returncode != 0
    assert "not found" in result.stderr


def test_backup_retention_keeps_last_14(workspace):
    """Any 15th file (older by mtime) should get pruned."""
    # Create 20 pre-existing "backups" with descending mtimes.
    for i in range(20):
        f = workspace["backups"] / f"foi-2020{i:02d}-000000Z.db.gz"
        workspace["backups"].mkdir(exist_ok=True)
        f.write_bytes(b"stub")
        ts = 1_000_000_000 + i * 86400  # each 1 day older than the next
        os.utime(f, (ts, ts))

    _run(BACKUP_SH)

    files = list(workspace["backups"].glob("foi-*.db.gz"))
    assert len(files) == 14
