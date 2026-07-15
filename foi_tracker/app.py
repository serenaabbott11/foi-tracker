# FOI Deadline Tracker — single-page app with a JSON API.

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from foi_tracker.audit import write_audit
from foi_tracker.deadlines import calculate_deadline

# Sentinel actor for requests made before HASEEB's login lands. AUD-3 will
# replace this with `current_user.username` in a single place.
_ACTOR_UNKNOWN = "unknown"

app = Flask(__name__)

_secret = os.environ.get("SECRET_KEY")
if not _secret:
    raise RuntimeError("SECRET_KEY environment variable must be set")
app.secret_key = _secret

# Default DB lives under <repo>/data/ so it does not sit next to source files
# and won't be wiped by an accidental `python -m scripts.seed` without --force.
# Override with FOI_DB.
_DEFAULT_DB = str(Path(__file__).resolve().parent.parent / "data" / "foi.db")
DB = os.environ.get("FOI_DB", _DEFAULT_DB)

STATUSES = ["Received", "In progress", "Internal review", "Responded", "Overdue"]

# Columns matched by the free-text search box. These are all-text columns —
# the SQL is built by joining these names with `OR`, so they must be a
# hard-coded allowlist (never user input).
SEARCHABLE_COLUMNS = ("ref", "requester", "subject", "received", "deadline", "status", "notes")


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def index():
    return render_template(
        "app.html",
        statuses=STATUSES,
        today=date.today().isoformat(),
    )


@app.get("/api/requests")
def list_requests():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        pattern = f"%{q.lower()}%"
        where = " OR ".join(f"LOWER({col}) LIKE ?" for col in SEARCHABLE_COLUMNS)
        rows = db.execute(
            f"SELECT * FROM requests WHERE {where} ORDER BY deadline",
            [pattern] * len(SEARCHABLE_COLUMNS),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM requests ORDER BY deadline").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/requests")
def create_request():
    data = request.get_json(silent=True) or request.form
    ref = data["ref"]
    requester = data["requester"]
    subject = data["subject"]
    received = data["received"]

    deadline = calculate_deadline(datetime.strptime(received, "%Y-%m-%d").date())

    db = get_db()
    cur = db.execute(
        "INSERT INTO requests (ref, requester, subject, received, deadline, status) "
        "VALUES (?, ?, ?, ?, ?, 'Received')",
        (ref, requester, subject, received, deadline.isoformat()),
    )
    new_id = cur.lastrowid
    write_audit(
        db,
        action="create",
        entity_type="request",
        entity_id=new_id,
        actor=_ACTOR_UNKNOWN,
        actor_ip=request.remote_addr,
        after={
            "ref": ref,
            "requester": requester,
            "subject": subject,
            "received": received,
            "deadline": deadline.isoformat(),
            "status": "Received",
        },
    )
    db.commit()
    return jsonify({"id": new_id, "deadline": deadline.isoformat()}), 201


@app.get("/api/requests/<int:req_id>")
def get_request(req_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM requests WHERE id = ?", (req_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    write_audit(
        db,
        action="view",
        entity_type="request",
        entity_id=req_id,
        actor=_ACTOR_UNKNOWN,
        actor_ip=request.remote_addr,
    )
    db.commit()
    return jsonify(dict(row))


@app.post("/api/requests/<int:req_id>")
def update_request(req_id):
    data = request.get_json(silent=True) or request.form
    status = data["status"]
    notes = data.get("notes", "")

    db = get_db()
    before_row = db.execute(
        "SELECT * FROM requests WHERE id = ?", (req_id,)
    ).fetchone()
    if before_row is None:
        return jsonify({"error": "not found"}), 404

    db.execute(
        "UPDATE requests SET status = ?, notes = ? WHERE id = ?",
        (status, notes, req_id),
    )
    write_audit(
        db,
        action="update",
        entity_type="request",
        entity_id=req_id,
        actor=_ACTOR_UNKNOWN,
        actor_ip=request.remote_addr,
        before={"status": before_row["status"], "notes": before_row["notes"]},
        after={"status": status, "notes": notes},
    )
    db.commit()
    return jsonify({"ok": True})
