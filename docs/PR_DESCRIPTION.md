# PR: `fix/security-hardening` → `main`

## Suggested title
```
fix: security hardening, single-page app, and repo restructure
```

## Description

### What
Three things, closest to the ICO audit first:

1. **Closed 4 SQL injection points in `app.py`.** Every user-supplied value
   now flows through a parameterised query (`?` placeholders); no more
   f-string SQL. Covers search, insert, update, and select-by-id.
2. **Removed unsafe production defaults.**
   - `SECRET_KEY` is now required from the environment — the app raises at
     startup if it's missing.
   - `debug=True` is gone. Debug is opt-in via `FLASK_DEBUG=1`.
   - DB path is configurable via `FOI_DB` (used by tests for isolation).
3. **Converted to a single-page app** — the previous multi-page layout broke
   under the lab proxy (`/proxy/5002/…`). Now `/` returns one HTML shell and
   the browser talks to `/api/requests[/{id}]` via `fetch()`.

### Also in this PR
- Repo restructured: `foi_tracker/` (app), `tests/`, `scripts/`, `docs/`.
- Added `CLAUDE.md` files (root, `foi_tracker/`, `tests/`) so the next
  contributor — human or AI — can pick up the security conventions cleanly.
- README rewritten to be short and readable.
- Change log at `docs/AI_LOG.md`.

### Tests
6 tests in `tests/test_security.py`, all passing:

- `test_search_blocks_sql_injection` — `?q=' OR 1=1--` returns `[]`.
- `test_search_returns_matching_row` — normal search still works.
- `test_new_request_handles_quotes_safely` — apostrophes in fields insert cleanly.
- `test_update_request_handles_quotes_safely` — apostrophes in notes update cleanly.
- `test_index_serves_single_page_shell` — `/` returns the SPA shell.
- `test_app_refuses_to_start_without_secret_key` — startup guard works.

Run with `python -m pytest`.

### How to run locally
```bash
pip install -r requirements.txt
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
python -m scripts.seed
python run.py
```
Open <http://localhost:5002>.

### Out of scope (intentionally)
- Bank-holiday-aware deadlines — Serena's task, tracked separately.
- Login / auth — Haseeb's follow-up (needed before the audit log).
- Audit log for status changes — Satyavrat, depends on login.
- Backups + GDPR — Teemerte.
