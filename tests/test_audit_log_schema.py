"""AUD-1: audit_log table + immutability triggers.

Tests that the schema installs cleanly, is idempotent, permits inserts, and
rejects UPDATE / DELETE via the triggers.
"""
import os
import sqlite3
import tempfile

import pytest

from scripts.migrate_add_audit_log import apply as apply_audit_log


@pytest.fixture
def conn():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    yield c
    c.close()
    os.remove(path)


def _insert_row(conn):
    conn.execute(
        "INSERT INTO audit_log "
        "(timestamp, actor, action, entity_type, entity_id, after_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-07-15T12:00:00Z", "test", "create", "request", "1", '{"a": 1}'),
    )
    conn.commit()


def test_apply_creates_table_and_triggers(conn):
    apply_audit_log(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "audit_log" in tables

    triggers = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )
    }
    assert "audit_log_no_update" in triggers
    assert "audit_log_no_delete" in triggers


def test_apply_is_idempotent(conn):
    apply_audit_log(conn)
    apply_audit_log(conn)  # should not raise
    apply_audit_log(conn)


def test_insert_is_permitted(conn):
    apply_audit_log(conn)
    _insert_row(conn)

    count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert count == 1


def test_update_is_rejected(conn):
    apply_audit_log(conn)
    _insert_row(conn)

    with pytest.raises(sqlite3.DatabaseError, match="audit log is immutable"):
        conn.execute("UPDATE audit_log SET actor = 'tamper' WHERE id = 1")


def test_delete_is_rejected(conn):
    apply_audit_log(conn)
    _insert_row(conn)

    with pytest.raises(sqlite3.DatabaseError, match="audit log is immutable"):
        conn.execute("DELETE FROM audit_log WHERE id = 1")

    # Row is still there.
    count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert count == 1


def test_seed_creates_audit_log_table():
    """seed.py should include the audit_log schema so a fresh DB is complete."""
    from scripts.seed import seed

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)

    try:
        seed(path)
        c = sqlite3.connect(path)
        tables = {
            row[0]
            for row in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "requests" in tables
        assert "audit_log" in tables
        c.close()
    finally:
        if os.path.exists(path):
            os.remove(path)
