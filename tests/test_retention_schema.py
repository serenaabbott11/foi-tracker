"""DP-1: retention columns migration.

Tests that the migration is idempotent, adds all expected columns, backfills
correctly, and that the app endpoints populate the new fields.
"""
import json
import os
import sqlite3
import sys
import tempfile

import pytest

from scripts.migrate_add_retention import _NEW_COLUMNS, apply as apply_retention


EXPECTED = {name for name, _ in _NEW_COLUMNS}


def _reload_app():
    for mod in list(sys.modules):
        if mod == "foi_tracker" or mod.startswith("foi_tracker."):
            sys.modules.pop(mod, None)


def _make_base_db(path: str) -> None:
    conn = sqlite3.connect(path)
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
        "VALUES ('FOI-DP1-A', 'a', 's', '2026-01-01', '2026-01-29', 'Received', '')"
    )
    conn.execute(
        "INSERT INTO requests (ref, requester, subject, received, deadline, status, notes) "
        "VALUES ('FOI-DP1-B', 'b', 's', '2026-01-02', '2026-01-30', 'Responded', '')"
    )
    conn.commit()
    conn.close()


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    _make_base_db(path)
    yield path
    os.remove(path)


def _columns(path: str) -> set[str]:
    conn = sqlite3.connect(path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(requests)")}
    conn.close()
    return cols


def test_migration_adds_all_columns(db_path):
    apply_retention(sqlite3.connect(db_path))
    cols = _columns(db_path)
    for name in EXPECTED:
        assert name in cols


def test_migration_is_idempotent(db_path):
    conn = sqlite3.connect(db_path)
    apply_retention(conn)
    apply_retention(conn)  # must not raise
    apply_retention(conn)
    conn.close()

    cols = _columns(db_path)
    for name in EXPECTED:
        assert name in cols


def test_backfill_created_and_updated_at_from_received(db_path):
    conn = sqlite3.connect(db_path)
    apply_retention(conn)

    rows = conn.execute(
        "SELECT received, created_at, updated_at FROM requests ORDER BY id"
    ).fetchall()
    conn.close()
    for received, created_at, updated_at in rows:
        assert created_at == received
        assert updated_at == received


def test_backfill_responded_at_only_when_status_is_responded(db_path):
    conn = sqlite3.connect(db_path)
    apply_retention(conn)

    rows = conn.execute(
        "SELECT status, received, responded_at FROM requests ORDER BY id"
    ).fetchall()
    conn.close()

    # First row is 'Received' -> responded_at NULL. Second is 'Responded' ->
    # responded_at backfilled from received.
    assert rows[0][0] == "Received"
    assert rows[0][2] is None
    assert rows[1][0] == "Responded"
    assert rows[1][2] == rows[1][1]


def test_migration_missing_requests_table_errors(tmp_path):
    empty = tmp_path / "empty.db"
    sqlite3.connect(str(empty)).close()  # empty DB, no `requests` table

    with pytest.raises(RuntimeError, match="requests table not found"):
        apply_retention(sqlite3.connect(str(empty)))


# --- app.py side: new inserts populate created_at / updated_at -------------


@pytest.fixture
def client_and_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    _make_base_db(path)

    from foi_tracker.audit import now_utc_iso
    from foi_tracker.auth import hash_password
    from scripts.migrate_add_audit_log import apply as apply_audit_log
    from scripts.migrate_add_users import apply as apply_users

    conn = sqlite3.connect(path)
    apply_audit_log(conn)
    apply_retention(conn)
    apply_users(conn)
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) "
        "VALUES (?, ?, ?, ?)",
        ("testuser", hash_password("testpass"), "caseworker", now_utc_iso()),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.setenv("FOI_DB", path)
    _reload_app()
    from foi_tracker.app import app as flask_app

    flask_app.config["TESTING"] = True
    tc = flask_app.test_client()
    tc.post("/login", data={"username": "testuser", "password": "testpass"})
    yield tc, path
    os.remove(path)


def test_create_sets_created_and_updated_at(client_and_db):
    client, db_path = client_and_db
    resp = client.post(
        "/api/requests",
        json={
            "ref": "FOI-DP1-X",
            "requester": "x",
            "subject": "s",
            "received": "2026-02-01",
        },
    )
    assert resp.status_code == 201
    new_id = resp.get_json()["id"]

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT created_at, updated_at, responded_at FROM requests WHERE id = ?",
        (new_id,),
    ).fetchone()
    conn.close()

    created_at, updated_at, responded_at = row
    assert created_at is not None
    assert updated_at is not None
    # Both timestamps for a fresh row are the same instant.
    assert created_at == updated_at
    assert responded_at is None
    # Must look like UTC ISO-8601.
    assert created_at.endswith("Z")


def test_update_bumps_updated_at_but_not_created_at(client_and_db):
    client, db_path = client_and_db
    # Baseline created_at
    conn = sqlite3.connect(db_path)
    row_before = conn.execute(
        "SELECT created_at, updated_at FROM requests WHERE id = 1"
    ).fetchone()
    conn.close()

    resp = client.post(
        "/api/requests/1",
        json={"status": "In progress", "notes": "picked up"},
    )
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    row_after = conn.execute(
        "SELECT created_at, updated_at, responded_at FROM requests WHERE id = 1"
    ).fetchone()
    conn.close()

    assert row_after[0] == row_before[0]  # created_at unchanged
    assert row_after[1] != row_before[1]  # updated_at bumped
    assert row_after[2] is None  # not transitioning to Responded


def test_update_to_responded_sets_responded_at(client_and_db):
    client, db_path = client_and_db
    resp = client.post(
        "/api/requests/1",
        json={"status": "Responded", "notes": "done"},
    )
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, responded_at, updated_at FROM requests WHERE id = 1"
    ).fetchone()
    conn.close()

    assert row[0] == "Responded"
    assert row[1] is not None  # responded_at now set
    assert row[1] == row[2]  # equals updated_at at the transition moment


def test_re_saving_responded_does_not_reset_responded_at(client_and_db):
    """If the status is already 'Responded', responded_at must not update."""
    client, db_path = client_and_db
    client.post("/api/requests/1", json={"status": "Responded", "notes": "first"})

    conn = sqlite3.connect(db_path)
    first_responded_at = conn.execute(
        "SELECT responded_at FROM requests WHERE id = 1"
    ).fetchone()[0]
    conn.close()

    # Now re-save with same status but different notes.
    client.post("/api/requests/1", json={"status": "Responded", "notes": "second"})

    conn = sqlite3.connect(db_path)
    second_responded_at = conn.execute(
        "SELECT responded_at FROM requests WHERE id = 1"
    ).fetchone()[0]
    conn.close()

    assert first_responded_at == second_responded_at
