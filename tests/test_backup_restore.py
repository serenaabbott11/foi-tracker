"""Proof that a backup can restore the database after data loss.

This is the evidence the ICO auditor asks for under "recoverability": not
"we take backups" but "we have proven a restore brings the data back".
"""
import sqlite3

from scripts.backup import make_backup, prune
from scripts.restore import latest_backup, restore


def _make_db(path, refs):
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE IF EXISTS requests")
    conn.execute("CREATE TABLE requests (id INTEGER PRIMARY KEY, ref TEXT)")
    conn.executemany(
        "INSERT INTO requests (ref) VALUES (?)", [(r,) for r in refs]
    )
    conn.commit()
    conn.close()


def _refs(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT ref FROM requests ORDER BY id")]
    finally:
        conn.close()


def test_backup_then_restore_recovers_lost_data(tmp_path):
    """Gary's disk dies: the live DB is gone, the backup brings it back."""
    db = tmp_path / "foi.db"
    backups = tmp_path / "backups"
    _make_db(db, ["FOI-1", "FOI-2", "FOI-3"])

    dest = make_backup(db_path=db, backup_dir=backups)
    assert dest.exists()

    # Disaster: the live database is destroyed.
    db.unlink()
    assert not db.exists()

    src, safety = restore(backup_path=dest, db_path=db)
    assert db.exists()
    assert _refs(db) == ["FOI-1", "FOI-2", "FOI-3"]
    assert safety is None  # there was nothing to preserve


def test_restore_from_latest_backup(tmp_path):
    """With no path given, restore picks the newest backup."""
    db = tmp_path / "foi.db"
    backups = tmp_path / "backups"
    _make_db(db, ["FOI-1"])
    make_backup(db_path=db, backup_dir=backups)

    assert latest_backup(backup_dir=backups).exists()


def test_restore_preserves_current_db(tmp_path):
    """A restore is reversible: the pre-restore state is copied aside first."""
    db = tmp_path / "foi.db"
    backups = tmp_path / "backups"
    _make_db(db, ["FOI-GOOD"])
    good = make_backup(db_path=db, backup_dir=backups)

    # The DB drifts to bad data; we roll back to the known-good backup.
    _make_db(db, ["FOI-JUNK"])
    src, safety = restore(backup_path=good, db_path=db)

    assert _refs(db) == ["FOI-GOOD"]
    assert safety is not None and safety.exists()
    assert _refs(safety) == ["FOI-JUNK"]  # the drifted state is recoverable


def test_prune_keeps_only_newest(tmp_path):
    """Old backups are pruned so the disk doesn't fill up."""
    db = tmp_path / "foi.db"
    backups = tmp_path / "backups"
    _make_db(db, ["FOI-1"])
    backups.mkdir()

    # Hand-place five valid backups with increasing timestamps.
    stamps = ["20260101-000000", "20260102-000000", "20260103-000000",
              "20260104-000000", "20260105-000000"]
    for stamp in stamps:
        (backups / f"foi-{stamp}.db").write_bytes(db.read_bytes())

    pruned = prune(backup_dir=backups, keep=2)
    remaining = sorted(p.name for p in backups.glob("foi-*.db"))

    assert remaining == ["foi-20260104-000000.db", "foi-20260105-000000.db"]
    assert len(pruned) == 3
