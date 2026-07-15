import os
import sqlite3
import sys
import tempfile

import pytest


@pytest.fixture
def client(monkeypatch):
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
    conn.commit()
    conn.close()

    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.setenv("FOI_DB", path)
    sys.modules.pop("app", None)
    from app import app as flask_app

    flask_app.config["TESTING"] = True
    yield flask_app.test_client()

    os.remove(path)


def test_search_blocks_sql_injection(client):
    # Classic injection: if unpatched, this would dump all rows
    response = client.get("/?q=' OR 1=1--")
    assert response.status_code == 200
    assert b"FOI-TEST-001" not in response.data


def test_search_returns_matching_row(client):
    response = client.get("/?q=Bridge")
    assert response.status_code == 200
    assert b"FOI-TEST-001" in response.data


def test_new_request_handles_quotes_safely(client):
    response = client.post(
        "/new",
        data={
            "ref": "FOI-2026-9999",
            "requester": "T. O'Brien",
            "subject": "Data on 'quoted' subjects",
            "received": "2026-01-05",
        },
    )
    assert response.status_code == 302

    listing = client.get("/")
    assert b"FOI-2026-9999" in listing.data


def test_update_request_handles_quotes_safely(client):
    response = client.post(
        "/request/1",
        data={"status": "In progress", "notes": "Note with 'apostrophe'"},
    )
    assert response.status_code == 302

    detail = client.get("/request/1")
    assert b"In progress" in detail.data


def test_app_refuses_to_start_without_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    sys.modules.pop("app", None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        import app  # noqa: F401
