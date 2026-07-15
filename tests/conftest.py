"""Shared pytest fixtures.

The `client` fixture builds a fresh SQLite DB with a small, deliberately varied
sample so search tests can exercise every column and mixed case.
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


def _reload_app():
    for mod in list(sys.modules):
        if mod == "foi_tracker" or mod.startswith("foi_tracker."):
            sys.modules.pop(mod, None)


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
    conn.executemany(
        "INSERT INTO requests (ref, requester, subject, received, deadline, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        SAMPLE_ROWS,
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
def reload_app():
    """Helper for tests that need to control module reloading themselves."""
    return _reload_app
