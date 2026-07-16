# FOI Deadline Tracker — single-page app with a JSON API.

import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request

from foi_tracker.audit import now_utc_iso, write_audit
from foi_tracker.deadlines import calculate_deadline
from foi_tracker.logging_config import new_request_id, setup_logging

# Sentinel actor for requests made before HASEEB's login lands. AUD-3 will
# replace this with `current_user.username` in a single place.
_ACTOR_UNKNOWN = "unknown"

setup_logging(
    log_dir=os.environ.get("LOG_DIR"),
    log_level=os.environ.get("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger("foi_tracker.app")

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

logger.info("FOI Deadline Tracker starting, db=%s", DB)


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


@app.before_request
def _assign_request_id():
    g.request_id = new_request_id()


@app.get("/")
def index():
    return render_template(
        "app.html",
        statuses=STATUSES,
        today=date.today().isoformat(),
    )


@app.get("/api/healthz")
def healthz():
    """OPS-6: liveness + DB reachability. Not audit-logged.

    Returns 200 + {"ok": true, "db": true} when both the app and the DB
    respond, else 503 with `db: false`. Used by container HEALTHCHECK
    and external monitors — must remain cheap and auth-free.
    """
    db_ok = False
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
        db_ok = True
    except sqlite3.Error as exc:
        db_ok = False
        logger.warning("healthz DB check failed: %s", exc)
    status_code = 200 if db_ok else 503
    return jsonify({"ok": db_ok, "db": db_ok}), status_code


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
    now = now_utc_iso()

    db = get_db()
    cur = db.execute(
        "INSERT INTO requests (ref, requester, subject, received, deadline, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'Received', ?, ?)",
        (ref, requester, subject, received, deadline.isoformat(), now, now),
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


@app.get("/api/requests/<int:req_id>/audit")
def request_audit(req_id):
    """AUD-5: per-request audit history — the ICO auditor's core question."""
    db = get_db()
    exists = db.execute(
        "SELECT id FROM requests WHERE id = ?", (req_id,)
    ).fetchone()
    if exists is None:
        return jsonify({"error": "not found"}), 404

    rows = db.execute(
        "SELECT id, timestamp, actor, actor_ip, action, "
        "       entity_type, entity_id, before_json, after_json, reason "
        "FROM audit_log "
        "WHERE entity_type = 'request' AND entity_id = ? "
        "ORDER BY id DESC",
        (str(req_id),),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# Columns allowed as filter fields on /api/audit — hardcoded allowlist,
# never user input, so f-string composition below is safe.
_AUDIT_FILTER_COLUMNS = {
    "action": "action",
    "actor": "actor",
    "entity_type": "entity_type",
    "entity_id": "entity_id",
}


def _audit_query(args) -> tuple[str, list]:
    """Build a WHERE clause + params from request.args for the audit views.

    Accepts: action, actor, entity_type, entity_id, from (>= ISO), to (<= ISO).
    Returns (sql_fragment, params). Fragment is empty or starts with WHERE.
    """
    clauses: list[str] = []
    params: list = []
    for arg_name, col in _AUDIT_FILTER_COLUMNS.items():
        val = args.get(arg_name)
        if val:
            clauses.append(f"{col} = ?")
            params.append(val)
    if args.get("from"):
        clauses.append("timestamp >= ?")
        params.append(args["from"])
    if args.get("to"):
        clauses.append("timestamp <= ?")
        params.append(args["to"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


@app.get("/api/audit")
def audit_index():
    """AUD-5: cross-request audit view.

    TODO(AUD-3 / DP-4): once login + roles land, restrict this to
    'admin' / 'foi_officer'. Today it is open — do not deploy to a
    public network until then.
    """
    where, params = _audit_query(request.args)
    try:
        limit = min(int(request.args.get("limit", "200")), 1000)
    except ValueError:
        limit = 200

    sql = f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?"
    params.append(limit)

    db = get_db()
    rows = db.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/audit.csv")
def audit_csv():
    """AUD-5: CSV export for auditors. Same filtering as /api/audit."""
    # TODO(AUD-3 / DP-4): admin-only once auth lands.
    import csv
    import io
    from datetime import datetime, timezone

    where, params = _audit_query(request.args)
    sql = f"SELECT * FROM audit_log {where} ORDER BY id"

    db = get_db()
    rows = db.execute(sql, params).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "timestamp", "actor", "actor_ip", "action",
        "entity_type", "entity_id", "before_json", "after_json", "reason",
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["timestamp"], r["actor"], r["actor_ip"], r["action"],
            r["entity_type"], r["entity_id"],
            r["before_json"] or "", r["after_json"] or "", r["reason"] or "",
        ])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="audit-{stamp}.csv"',
        },
    )


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

    now = now_utc_iso()
    # responded_at is set on the transition to 'Responded' (only if not
    # already set). Uses SQL CASE so the update is atomic and re-transitioning
    # doesn't clobber the original responded_at.
    db.execute(
        "UPDATE requests SET status = ?, notes = ?, updated_at = ?, "
        "responded_at = CASE "
        "  WHEN ? = 'Responded' AND responded_at IS NULL THEN ? "
        "  ELSE responded_at END "
        "WHERE id = ?",
        (status, notes, now, status, now, req_id),
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
