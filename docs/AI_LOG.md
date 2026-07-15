# AI Change Log

## 2026-07-15 — Single-page app (Haseeb, assisted by Claude)

**Why:** the lab proxy at `/proxy/5002/` breaks server-rendered navigation —
clicking a row went to `/request/1` instead of `/proxy/5002/request/1`,
so users couldn't test the app at all.

**What changed:**
- `/` now returns one HTML shell (`foi_tracker/templates/app.html`).
- Data moved behind a JSON API: `GET/POST /api/requests`,
  `GET/POST /api/requests/<id>`.
- List, new-request form, and detail/edit are panels in the same page,
  driven by vanilla JS with `fetch()`. All fetch URLs are relative
  (`api/requests`, not `/api/…`) so they resolve under the proxy prefix.
- `<base href="./">` in the shell locks the URL base to the current path.
- Old templates (`base.html`, `index.html`, `new.html`, `detail.html`) removed.
- SQL still parameterised, `SECRET_KEY` still required — security rules
  from the previous change are preserved and tested.

**Tests:** 6 tests pass (`test_index_serves_single_page_shell` added;
existing four SQL injection tests updated to hit the API endpoints).

---

## 2026-07-15 — Security hardening + repo reorganisation (Haseeb, assisted by Claude)

**Branch:** `fix/security-hardening`

### Security fixes
- Replaced 4 f-string SQL queries with parameterised queries (search, insert, update, select by id).
- Moved `SECRET_KEY` from hard-coded `"dev"` to a required environment variable. App raises `RuntimeError` at startup if unset.
- Removed hard-coded `debug=True`. Opt-in via `FLASK_DEBUG=1`, default off.
- Made DB path configurable via `FOI_DB` env var (used by tests for isolation).

### Why
- SQL injection in the search box was exploitable with any input containing `'`. ICO audit would flag this.
- `secret_key = "dev"` in production is a session-hijack risk.
- `debug=True` in production leaks stack traces and enables the Werkzeug debugger (RCE).

### Repo reorganisation
Flat layout → package layout:

```
foi_tracker/     Application package (app + routes + deadlines + templates)
tests/           Pytest suite
scripts/         seed.py
docs/            AI_LOG, TEAM-PLAN, hackathon brief
run.py           Entry point
pytest.ini       Test config
```

### Tests (`tests/test_security.py`)
- `test_search_blocks_sql_injection` — `?q=' OR 1=1--` returns no data.
- `test_search_returns_matching_row` — normal search still works.
- `test_new_request_handles_quotes_safely` — apostrophes in fields insert cleanly.
- `test_update_request_handles_quotes_safely` — apostrophes in notes update cleanly.
- `test_app_refuses_to_start_without_secret_key` — app raises without `SECRET_KEY`.

All 5 pass.

### Run
```
pip install -r requirements.txt
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
python -m scripts.seed
python run.py
```

Tests:
```
python -m pytest
```
