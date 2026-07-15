# AI Change Log

## 2026-07-15 — Security hardening (Haseeb, assisted by Claude Sonnet 4.6)

**Branch:** `fix/security-hardening`
**Files:** `app.py`, `test_app.py`, `requirements.txt`

### What changed
- Replaced 4 f-string SQL queries in `app.py` with parameterised queries (search, insert, update, select by id).
- Moved `SECRET_KEY` from hard-coded `"dev"` to a required environment variable. App raises `RuntimeError` at startup if unset.
- Removed hard-coded `debug=True`. Now opt-in via `FLASK_DEBUG=1`, default off.
- Made DB path configurable via `FOI_DB` env var so tests use an isolated database.

### Why
- SQL injection in the search box (and every write path) was exploitable with any input containing `'`. ICO audit would flag this immediately.
- `secret_key = "dev"` in a production app is a session-hijack risk.
- `debug=True` in production leaks stack traces and enables the Werkzeug debugger (RCE).

### Tests added (`test_app.py`)
- `test_search_blocks_sql_injection` — `?q=' OR 1=1--` returns no data.
- `test_search_returns_matching_row` — normal search still works.
- `test_new_request_handles_quotes_safely` — apostrophes in fields insert cleanly.
- `test_update_request_handles_quotes_safely` — apostrophes in notes update cleanly.
- `test_app_refuses_to_start_without_secret_key` — app raises without `SECRET_KEY`.

All 5 tests pass.

### How to run
```
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
python seed.py
python app.py
```

To run tests:
```
python -m pytest test_app.py -v
```
