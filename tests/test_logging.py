"""OPS-5: structured logging setup and per-request id."""
import logging
import re

import pytest

from foi_tracker.logging_config import (
    LOG_DATEFMT,
    LOG_FORMAT,
    _RequestIDFilter,
    new_request_id,
    setup_logging,
)


def test_new_request_id_is_short_hex():
    rid = new_request_id()
    assert len(rid) == 8
    assert all(c in "0123456789abcdef" for c in rid)
    # Uniqueness across a small batch (probabilistic — 8 hex chars is enough).
    ids = {new_request_id() for _ in range(50)}
    assert len(ids) == 50


def test_request_id_filter_defaults_to_dash_outside_request(caplog):
    f = _RequestIDFilter()
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 0, "hello", (), None
    )
    assert f.filter(record) is True
    assert record.request_id == "-"


def test_setup_logging_is_idempotent():
    setup_logging()
    root = logging.getLogger("foi_tracker")
    n = len(root.handlers)
    setup_logging()
    setup_logging()
    assert len(root.handlers) == n


def test_log_format_produces_expected_shape():
    """Concrete rendering: the formatter output must contain ts, level, logger,
    request_id in brackets, and the message — in that order."""
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
    record = logging.LogRecord(
        "foi_tracker.app", logging.INFO, __file__, 0,
        "hello world", (), None,
    )
    record.request_id = "abc12345"
    line = formatter.format(record)
    # e.g. "2026-07-15T12:00:00Z INFO foi_tracker.app [abc12345] hello world"
    pattern = (
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z "
        r"INFO foi_tracker\.app \[abc12345\] hello world$"
    )
    assert re.match(pattern, line), line


def test_request_id_populated_during_flask_request(client, caplog):
    """Inside a real request context, g.request_id ends up on log records."""
    caplog.set_level(logging.INFO, logger="foi_tracker")

    from foi_tracker.app import app as flask_app

    with flask_app.test_request_context("/api/healthz"):
        # Trigger the before_request handler manually.
        flask_app.preprocess_request()
        logger = logging.getLogger("foi_tracker.test")
        record = logging.LogRecord(
            "foi_tracker.test", logging.INFO, __file__, 0,
            "hi from a request", (), None,
        )
        _RequestIDFilter().filter(record)

    # Inside a request context, the filter should have picked g.request_id.
    assert record.request_id != "-"
    assert len(record.request_id) == 8
