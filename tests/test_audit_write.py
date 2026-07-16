"""AUD-2: every write and every specific-row read produces an audit_log row."""
import json
import os
import sqlite3
import sys
import tempfile

import pytest


def _reload_app():
    for mod in list(sys.modules):
        if mod == "foi_tracker" or mod.startswith("foi_tracker."):
            sys.modules.pop(mod, None)


@pytest.fixture
def client_and_db(monkeypatch):
    """Test client plus the DB path, so tests can read audit_log directly."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

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
        "VALUES ('FOI-TEST-001', 'A. Tester', 'Bridge inspections', "
        "'2026-01-01', '2026-01-29', 'Received', '')"
    )
    from foi_tracker.audit import now_utc_iso
    from foi_tracker.auth import hash_password
    from scripts.migrate_add_audit_log import apply as apply_audit_log
    from scripts.migrate_add_retention import apply as apply_retention
    from scripts.migrate_add_users import apply as apply_users

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


def _audit_rows(db_path):
    """Only request-scoped audit rows. Excludes login/logout rows added by
    the fixture, so per-test row counts stay meaningful."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE entity_type = 'request' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def test_create_writes_audit_row(client_and_db):
    client, db_path = client_and_db
    resp = client.post(
        "/api/requests",
        json={
            "ref": "FOI-AUD-1",
            "requester": "Test Requester",
            "subject": "test create",
            "received": "2026-01-05",
        },
    )
    assert resp.status_code == 201
    new_id = resp.get_json()["id"]

    rows = _audit_rows(db_path)
    assert len(rows) == 1
    r = rows[0]
    assert r["action"] == "create"
    assert r["entity_type"] == "request"
    assert r["entity_id"] == str(new_id)
    assert r["actor"] == "testuser"  # AUD-3 now populates actor from current_user
    assert r["before_json"] is None
    after = json.loads(r["after_json"])
    assert after["ref"] == "FOI-AUD-1"
    assert after["status"] == "Received"


def test_view_writes_audit_row(client_and_db):
    client, db_path = client_and_db
    resp = client.get("/api/requests/1")
    assert resp.status_code == 200

    rows = _audit_rows(db_path)
    assert len(rows) == 1
    r = rows[0]
    assert r["action"] == "view"
    assert r["entity_type"] == "request"
    assert r["entity_id"] == "1"
    assert r["actor"] == "testuser"  # AUD-3 now populates actor from current_user
    assert r["before_json"] is None
    assert r["after_json"] is None


def test_update_writes_audit_row_with_before_and_after(client_and_db):
    client, db_path = client_and_db
    resp = client.post(
        "/api/requests/1",
        json={"status": "In progress", "notes": "started"},
    )
    assert resp.status_code == 200

    updates = [r for r in _audit_rows(db_path) if r["action"] == "update"]
    assert len(updates) == 1
    r = updates[0]
    assert r["entity_id"] == "1"
    before = json.loads(r["before_json"])
    after = json.loads(r["after_json"])
    assert before["status"] == "Received"
    assert after["status"] == "In progress"
    assert after["notes"] == "started"


def test_update_missing_row_returns_404_and_no_audit(client_and_db):
    client, db_path = client_and_db
    resp = client.post(
        "/api/requests/9999",
        json={"status": "In progress", "notes": ""},
    )
    assert resp.status_code == 404

    rows = _audit_rows(db_path)
    assert rows == []


def test_list_does_not_write_audit_row(client_and_db):
    client, db_path = client_and_db
    resp = client.get("/api/requests")
    assert resp.status_code == 200

    rows = _audit_rows(db_path)
    assert rows == []


def test_view_missing_row_returns_404_and_no_audit(client_and_db):
    client, db_path = client_and_db
    resp = client.get("/api/requests/9999")
    assert resp.status_code == 404

    rows = _audit_rows(db_path)
    assert rows == []


def test_actor_ip_is_recorded(client_and_db):
    client, db_path = client_and_db
    client.get("/api/requests/1")

    rows = _audit_rows(db_path)
    assert len(rows) == 1
    # Flask's test client uses 127.0.0.1 by default.
    assert rows[0]["actor_ip"] == "127.0.0.1"
