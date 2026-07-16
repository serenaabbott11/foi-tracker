"""OPS-5: structured logging setup for the FOI Deadline Tracker.

Not the audit log — this is ops logging (startup, errors, warnings, backup
outcomes). Format includes a per-request short id so lines from one HTTP
request can be correlated in the log stream.

Callers:
    setup_logging(log_dir=os.environ.get("LOG_DIR"),
                  log_level=os.environ.get("LOG_LEVEL", "INFO"))

Log format:
    2026-07-15T12:00:00Z INFO foi_tracker [ab12cd34] starting, db=/data/foi.db
"""
import logging
import logging.handlers
import os
import sys
import uuid
from pathlib import Path
from typing import Optional


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s %(user)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%SZ"


class _RequestIDFilter(logging.Filter):
    """Add `request_id` and `user` to every LogRecord.

    Pulls both from Flask/Flask-Login when we're inside a request context,
    else falls back to '-'. Kept resilient — a logging call must never
    raise inside its own handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = "-"
        record.user = "-"
        try:
            from flask import g, has_request_context

            if has_request_context():
                record.request_id = getattr(g, "request_id", "-")
                try:
                    from flask_login import current_user

                    if current_user.is_authenticated:
                        record.user = current_user.username
                    else:
                        record.user = "anonymous"
                except Exception:
                    # flask-login not wired, or user_loader failed. Fall through.
                    pass
        except Exception:
            # Something unusual — keep the defaults.
            pass
        return True


def setup_logging(
    *,
    log_dir: Optional[str] = None,
    log_level: str = "INFO",
) -> None:
    """Configure the `foi_tracker` logger.

    Always writes to stdout (container-friendly). If `log_dir` is set,
    additionally writes to `<log_dir>/app.log` under a rotating handler
    (10 MB × 5 files).
    """
    root = logging.getLogger("foi_tracker")
    # Idempotent: avoid double-installing handlers on re-import (e.g. tests
    # that reload the module).
    if getattr(root, "_foi_configured", False):
        return

    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.propagate = False

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
    request_id_filter = _RequestIDFilter()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    stream.addFilter(request_id_filter)
    root.addHandler(stream)

    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        fh.setFormatter(formatter)
        fh.addFilter(request_id_filter)
        root.addHandler(fh)

    root._foi_configured = True  # type: ignore[attr-defined]


def new_request_id() -> str:
    """A short hex id for use in Flask's before_request → g.request_id."""
    return uuid.uuid4().hex[:8]
