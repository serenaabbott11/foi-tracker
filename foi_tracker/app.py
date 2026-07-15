# FOI Deadline Tracker — single-page app with a JSON API.

import os
import sqlite3
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request

from foi_tracker.deadlines import calculate_deadline

app = Flask(__name__)

_secret = os.environ.get("SECRET_KEY")
if not _secret:
    raise RuntimeError("SECRET_KEY environment variable must be set")
app.secret_key = _secret

DB = os.environ.get("FOI_DB", "foi.db")

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
    db.commit()
    return jsonify({"id": cur.lastrowid, "deadline": deadline.isoformat()}), 201


@app.get("/api/requests/<int:req_id>")
def get_request(req_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM requests WHERE id = ?", (req_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


@app.post("/api/requests/<int:req_id>")
def update_request(req_id):
    data = request.get_json(silent=True) or request.form
    status = data["status"]
    notes = data.get("notes", "")
    db = get_db()
    db.execute(
        "UPDATE requests SET status = ?, notes = ? WHERE id = ?",
        (status, notes, req_id),
    )
    db.commit()
    return jsonify({"ok": True})
