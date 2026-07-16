"""Shared pytest fixtures.

`anon_client` — Flask test client, DB populated with SAMPLE_ROWS and a
    `testuser` account. **Not** logged in — for auth tests.

`client` — same fixture, but already logged in as `testuser`. Everything
    that isn't an auth test uses this.

Each fixture creates its own temp DB and drops it on teardown.
"""
import os
import sqlite3
import sys
import tempfile

import pytest


SAMPLE_ROWS = [
    # (ref, requester, subject, received, deadline, status, notes)
    ("FOI-2026-0001", "A. Bridges",     "Rail electrification plans",   "2026-01-01", "2026-01-29", "Received",       ""),
    ("FOI-2026-0002", "Kent Online",    "Lower Thames Crossing costs",  "2026-01-05", "2026-02-02", "In progress",    "Draft response with legal"),
    ("FOI-2026-0003", "T. O'Brien",     "Bus service reallocations",    "2026-01-10", "2026-02-09", "Responded",      "Sent 2026-01-30"),
    ("FOI-2026-0004", "Cycling UK",     "Active travel budget",         "2026-01-15", "2026-02-12", "Overdue",        "Awaiting minister sign-off"),
    ("FOI-2026-0005", "The Herald",     "Pavement parking consultation","2026-01-20", "2026-02-17", "Internal review", ""),
]

TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass"
ADMIN_USERNAME = "testadmin"
ADMIN_PASSWORD = "adminpass"


def _reload_app():
    for mod in list(sys.modules):
        if mod == "foi_tracker" or mod.startswith("foi_tracker."):
            sys.modules.pop(mod, None)


@pytest.fixture
def anon_client(monkeypatch):
    """Test client with a fully-populated DB and a `testuser` account — but
    not signed in. Auth tests use this directly; everything else composes
    over it via the `client` fixture below."""
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
    conn.executemany(
        "INSERT INTO requests (ref, requester, subject, received, deadline, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        SAMPLE_ROWS,
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
        (TEST_USERNAME, hash_password(TEST_PASSWORD), "caseworker", now_utc_iso()),
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, role, created_at) "
        "VALUES (?, ?, ?, ?)",
        (ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "admin", now_utc_iso()),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.setenv("FOI_DB", path)
    _reload_app()
    from foi_tracker.app import app as flask_app

    flask_app.config["TESTING"] = True
    yield flask_app.test_client()
    os.remove(path)


@pytest.fixture
def client(anon_client):
    """Signed-in test client. Most tests want this."""
    resp = anon_client.post(
        "/login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 302, (
        f"fixture login failed: got {resp.status_code}, body={resp.data!r}"
    )
    yield anon_client


@pytest.fixture
def admin_client(anon_client):
    """Signed-in test client with admin role. Use for admin-only endpoint tests."""
    resp = anon_client.post(
        "/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 302, (
        f"admin fixture login failed: got {resp.status_code}, body={resp.data!r}"
    )
    yield anon_client


@pytest.fixture
def reload_app():
    """Helper for tests that need to control module reloading themselves."""
    return _reload_app
