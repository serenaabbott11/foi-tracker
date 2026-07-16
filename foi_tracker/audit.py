"""AUD-2: helper for writing audit_log rows.

Callers own the connection and the commit. This helper only INSERTs; it does
not commit, so the audit row lands atomically with the caller's change.

`actor` defaults to 'unknown' — the sentinel used while HASEEB's login work is
not yet merged (see plan.md §AUD-3). Once login lands, replace the default
with `current_user.username` here.
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dumps(obj: Optional[dict]) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj, default=str, sort_keys=True)


def write_audit(
    conn: sqlite3.Connection,
    *,
    action: str,
    entity_type: str,
    entity_id: Optional[Any] = None,
    actor: str = "unknown",
    actor_ip: Optional[str] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    reason: Optional[str] = None,
) -> None:
    """Insert one row into audit_log. Does not commit."""
    conn.execute(
        "INSERT INTO audit_log "
        "(timestamp, actor, actor_ip, action, entity_type, entity_id, "
        " before_json, after_json, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            now_utc_iso(),
            actor,
            actor_ip,
            action,
            entity_type,
            None if entity_id is None else str(entity_id),
            _dumps(before),
            _dumps(after),
            reason,
        ),
    )
