"""OPS-6: /api/healthz — cheap liveness + DB reachability probe."""


def test_healthz_ok_when_db_is_reachable(client):
    resp = client.get("/api/healthz")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"ok": True, "db": True}


def test_healthz_does_not_write_audit_row(client):
    """The healthcheck must not spam audit_log — cron/HEALTHCHECK hit it often."""
    import os
    import sqlite3

    db_path = os.environ["FOI_DB"]
    conn = sqlite3.connect(db_path)
    before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()

    for _ in range(3):
        client.get("/api/healthz")

    conn = sqlite3.connect(db_path)
    after = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    assert after == before
