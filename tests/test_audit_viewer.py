"""AUD-5: audit viewer endpoints — per-request, cross-request, CSV export."""
import csv
import io
import json


# --- per-request audit --------------------------------------------------------


def test_per_request_audit_returns_only_that_requests_rows(client):
    # Interact with request 1 and request 2 to create audit rows on both.
    client.get("/api/requests/1")
    client.post("/api/requests/1", json={"status": "In progress", "notes": ""})
    client.get("/api/requests/2")

    resp = client.get("/api/requests/1/audit")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert all(r["entity_id"] == "1" for r in rows)
    actions = {r["action"] for r in rows}
    assert "view" in actions
    assert "update" in actions


def test_per_request_audit_is_newest_first(client):
    client.get("/api/requests/1")
    client.post("/api/requests/1", json={"status": "In progress", "notes": ""})
    client.get("/api/requests/1")

    rows = client.get("/api/requests/1/audit").get_json()
    # id descending — newest first — is the UI's expected order.
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids, reverse=True)


def test_per_request_audit_404_for_missing_request(client):
    resp = client.get("/api/requests/9999/audit")
    assert resp.status_code == 404


def test_per_request_audit_carries_before_after_diff(client):
    """The whole point of the audit trail — before/after must survive to the API."""
    client.post("/api/requests/1", json={"status": "Responded", "notes": "sent"})

    rows = client.get("/api/requests/1/audit").get_json()
    updates = [r for r in rows if r["action"] == "update"]
    assert updates, "no update row seen"
    row = updates[0]
    before = json.loads(row["before_json"])
    after = json.loads(row["after_json"])
    assert after["status"] == "Responded"
    assert before["status"] != "Responded"


# --- cross-request /api/audit — admin only ------------------------------------


def test_audit_index_returns_recent_rows(admin_client):
    # Generate a few rows.
    admin_client.get("/api/requests/1")
    admin_client.get("/api/requests/2")
    admin_client.post("/api/requests/1", json={"status": "In progress", "notes": ""})

    resp = admin_client.get("/api/audit")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) >= 3
    # Newest first
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids, reverse=True)


def test_audit_index_filter_by_action(admin_client):
    admin_client.get("/api/requests/1")
    admin_client.get("/api/requests/2")
    admin_client.post("/api/requests/1", json={"status": "In progress", "notes": ""})

    resp = admin_client.get("/api/audit?action=view")
    rows = resp.get_json()
    assert rows, "no view rows"
    assert all(r["action"] == "view" for r in rows)


def test_audit_index_filter_by_entity(admin_client):
    admin_client.get("/api/requests/1")
    admin_client.get("/api/requests/2")

    resp = admin_client.get("/api/audit?entity_type=request&entity_id=2")
    rows = resp.get_json()
    assert rows, "no rows for request 2"
    assert all(r["entity_id"] == "2" for r in rows)


def test_audit_index_limit_is_capped(admin_client):
    """Prevent an accidental DoS via limit=10000000."""
    for _ in range(5):
        admin_client.get("/api/requests/1")

    resp = admin_client.get("/api/audit?limit=999999999")
    assert resp.status_code == 200
    rows = resp.get_json()
    # The endpoint clamps to 1000. Not asserting exact length here — just
    # verifying it didn't blow up returning millions.
    assert len(rows) <= 1000


def test_audit_index_ignores_bogus_limit(admin_client):
    admin_client.get("/api/requests/1")
    resp = admin_client.get("/api/audit?limit=notanumber")
    assert resp.status_code == 200


def test_audit_index_non_admin_gets_403(client):
    """Caseworkers must not be able to reach the cross-request audit view."""
    resp = client.get("/api/audit")
    assert resp.status_code == 403


# --- CSV export — admin only --------------------------------------------------


def test_audit_csv_returns_csv_shape(admin_client):
    admin_client.get("/api/requests/1")
    admin_client.post("/api/requests/1", json={"status": "In progress", "notes": "abc"})

    resp = admin_client.get("/api/audit.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers.get("Content-Disposition", "")

    reader = csv.reader(io.StringIO(resp.get_data(as_text=True)))
    header = next(reader)
    assert header == [
        "id", "timestamp", "actor", "actor_ip", "action",
        "entity_type", "entity_id", "before_json", "after_json", "reason",
    ]
    body = list(reader)
    assert len(body) >= 2  # at least the view + update we just made


def test_audit_csv_filter_applies(admin_client):
    admin_client.get("/api/requests/1")
    admin_client.get("/api/requests/2")
    admin_client.post("/api/requests/1", json={"status": "In progress", "notes": ""})

    resp = admin_client.get("/api/audit.csv?action=view")
    reader = csv.reader(io.StringIO(resp.get_data(as_text=True)))
    header = next(reader)
    action_idx = header.index("action")
    for row in reader:
        assert row[action_idx] == "view"


def test_audit_csv_handles_commas_and_quotes_in_data(admin_client):
    """csv.writer must correctly quote fields containing our separator + quotes.

    JSON encodes internal `"` as `\\"`, so we check the round-trip by parsing
    the after_json cell and comparing the decoded string, not by substring.
    """
    payload_notes = 'a, comma and a "quote"'
    admin_client.post(
        "/api/requests/1",
        json={"status": "In progress", "notes": payload_notes},
    )

    resp = admin_client.get("/api/audit.csv?action=update")
    text = resp.get_data(as_text=True)
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    after_idx = header.index("after_json")

    found = False
    for row in reader:
        if not row[after_idx]:
            continue
        try:
            decoded = json.loads(row[after_idx])
        except json.JSONDecodeError:
            continue
        if decoded.get("notes") == payload_notes:
            found = True
            break
    assert found, "CSV round-trip did not preserve the special-character payload"


def test_audit_csv_non_admin_gets_403(client):
    """Caseworkers must not be able to download the audit CSV."""
    resp = client.get("/api/audit.csv")
    assert resp.status_code == 403
