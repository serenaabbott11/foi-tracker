"""Auth: login, logout, endpoint protection, and audit-log integration.

Uses `anon_client` (not signed in) throughout. The `client` fixture is
already signed-in — the wrong tool for testing the sign-in flow itself.
"""
import sqlite3

from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def _read_audit(db_path, action):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE action = ? ORDER BY id DESC",
        (action,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _db_path_from_env(monkeypatch=None):
    import os
    return os.environ["FOI_DB"]


# --- endpoint protection ----------------------------------------------------


def test_api_requests_requires_login(anon_client):
    resp = anon_client.get("/api/requests")
    assert resp.status_code == 401
    body = resp.get_json()
    assert body == {"error": "authentication required"}


def test_api_request_detail_requires_login(anon_client):
    resp = anon_client.get("/api/requests/1")
    assert resp.status_code == 401


def test_api_audit_requires_login(anon_client):
    resp = anon_client.get("/api/audit")
    assert resp.status_code == 401


def test_api_audit_csv_requires_login(anon_client):
    resp = anon_client.get("/api/audit.csv")
    assert resp.status_code == 401


def test_healthz_does_not_require_login(anon_client):
    """External monitors must be able to probe without credentials."""
    resp = anon_client.get("/api/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "db": True}


def test_index_redirects_unauthenticated_to_login(anon_client):
    resp = anon_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


# --- login form -------------------------------------------------------------


def test_login_page_renders(anon_client):
    resp = anon_client.get("/login")
    assert resp.status_code == 200
    assert b"Sign in" in resp.data


def test_login_page_when_already_authed_redirects_to_index(client):
    resp = client.get("/login")
    assert resp.status_code == 302
    # follow to `/` (also 302 to /login if not authed, 200 if authed).
    assert resp.headers.get("Location", "").endswith("/")


# --- login POST ------------------------------------------------------------


def test_login_success_sets_session_and_redirects(anon_client):
    resp = anon_client.post(
        "/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 302
    # Follow-up API call now succeeds without providing creds again.
    resp2 = anon_client.get("/api/requests")
    assert resp2.status_code == 200


def test_login_writes_login_audit_row(anon_client, monkeypatch):
    anon_client.post(
        "/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    rows = _read_audit(_db_path_from_env(), "login")
    assert rows, "no login audit row"
    r = rows[0]
    assert r["actor"] == TEST_USERNAME
    assert r["entity_type"] == "user"
    assert r["actor_ip"] == "127.0.0.1"


def test_login_wrong_password_returns_401(anon_client):
    resp = anon_client.post(
        "/login", data={"username": TEST_USERNAME, "password": "not-the-password"}
    )
    assert resp.status_code == 401
    assert b"not recognised" in resp.data


def test_login_wrong_password_writes_login_failed_audit(anon_client):
    anon_client.post(
        "/login", data={"username": TEST_USERNAME, "password": "not-the-password"}
    )
    rows = _read_audit(_db_path_from_env(), "login_failed")
    assert rows, "no login_failed audit row"
    r = rows[0]
    assert r["actor"] == "anonymous"
    assert TEST_USERNAME in (r["reason"] or "")


def test_login_unknown_user_writes_login_failed_audit(anon_client):
    anon_client.post(
        "/login", data={"username": "no-such-user", "password": "whatever"}
    )
    rows = _read_audit(_db_path_from_env(), "login_failed")
    assert rows, "no login_failed audit row"
    assert "no-such-user" in (rows[0]["reason"] or "")


def test_login_wrong_password_does_not_leak_which_field_was_wrong(anon_client):
    """We must not tell the attacker if the username exists — same message either way."""
    resp1 = anon_client.post(
        "/login", data={"username": TEST_USERNAME, "password": "wrong"}
    )
    resp2 = anon_client.post(
        "/login", data={"username": "no-such-user", "password": "wrong"}
    )
    assert resp1.data == resp2.data


def test_login_next_param_only_allows_same_site_paths(anon_client):
    """A malicious `next=//evil.example.com` must not send the user off-site."""
    resp = anon_client.post(
        "/login",
        data={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "next": "//evil.example.com/steal",
        },
    )
    assert resp.status_code == 302
    loc = resp.headers.get("Location", "")
    assert "evil.example.com" not in loc
    assert loc.endswith("/")


# --- logout ---------------------------------------------------------------


def test_logout_clears_session_and_next_call_401s(client):
    resp = client.post("/logout")
    assert resp.status_code == 302

    resp2 = client.get("/api/requests")
    assert resp2.status_code == 401


def test_logout_writes_logout_audit_row(client, monkeypatch):
    client.post("/logout")
    rows = _read_audit(_db_path_from_env(), "logout")
    assert rows, "no logout audit row"
    assert rows[0]["actor"] == TEST_USERNAME


def test_logout_requires_login(anon_client):
    resp = anon_client.post("/logout")
    # Not logged in -> unauthorized handler kicks in. Non-API path, so redirect.
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


# --- AUD-3: audit rows for actions carry the real username -----------------


def test_authenticated_view_records_username_in_audit(client):
    client.get("/api/requests/1")
    rows = _read_audit(_db_path_from_env(), "view")
    assert rows, "no view audit row"
    assert rows[0]["actor"] == TEST_USERNAME


def test_authenticated_update_records_username_in_audit(client):
    client.post(
        "/api/requests/1",
        json={"status": "In progress", "notes": "picked up"},
    )
    rows = _read_audit(_db_path_from_env(), "update")
    assert rows, "no update audit row"
    assert rows[0]["actor"] == TEST_USERNAME
