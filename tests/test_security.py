"""Security tests: SQL injection is closed and unsafe defaults are gone."""
import pytest


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
    conn.execute(
        "INSERT INTO requests (ref, requester, subject, received, deadline, status, notes) "
        "VALUES ('FOI-TEST-001', 'A. Tester', 'Bridge inspections', "
        "'2026-01-01', '2026-01-29', 'Received', '')"
    )
    # AUD-1: endpoints write to audit_log, so the fixture DB must have it.
    from scripts.migrate_add_audit_log import apply as apply_audit_log

    apply_audit_log(conn)
    conn.commit()
    conn.close()

    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.setenv("FOI_DB", path)
    _reload_app()
    from foi_tracker.app import app as flask_app

    flask_app.config["TESTING"] = True
    yield flask_app.test_client()

    os.remove(path)


def test_search_blocks_sql_injection(client):
    """Classic ' OR 1=1-- attack must not dump the table."""
    response = client.get("/api/requests?q=' OR 1=1--")
    assert response.status_code == 200
    assert response.get_json() == []


def test_new_request_handles_quotes_safely(client):
    response = client.post(
        "/api/requests",
        json={
            "ref": "FOI-2026-9999",
            "requester": "T. O'Brien",
            "subject": "Data on 'quoted' subjects",
            "received": "2026-01-05",
        },
    )
    assert response.status_code == 201

    listing = client.get("/api/requests").get_json()
    assert any(r["ref"] == "FOI-2026-9999" for r in listing)


def test_update_request_handles_quotes_safely(client):
    response = client.post(
        "/api/requests/1",
        json={"status": "In progress", "notes": "Note with 'apostrophe'"},
    )
    assert response.status_code == 200

    detail = client.get("/api/requests/1").get_json()
    assert detail["status"] == "In progress"
    assert detail["notes"] == "Note with 'apostrophe'"


def test_index_serves_single_page_shell(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"FOI Deadline Tracker" in response.data
    assert b"loadList()" in response.data


def test_app_refuses_to_start_without_secret_key(monkeypatch, reload_app):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    reload_app()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        import foi_tracker.app  # noqa: F401
