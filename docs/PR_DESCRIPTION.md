# PR: `fix/security-hardening` → `main`

## Suggested title
```
fix: security hardening, single-page app, and repo restructure
```

---

## Summary

Three things closest to the ICO audit, plus the cleanup they made unavoidable:

1. **Closed 4 SQL injection points** — search, insert, update, select-by-id.
2. **Removed unsafe production defaults** — `SECRET_KEY` required, `debug=True` gone.
3. **Converted to a single-page app** — the multi-page version broke under the lab proxy.
4. **Restructured the repo** into `foi_tracker/` / `tests/` / `scripts/` / `docs/`.
5. **Added tests** (6 in total) and Claude/human context docs.

---

## What changed and why

### 1. SQL injection — closed (`foi_tracker/app.py`)

**Why:** the search box and every write path were built with f-string queries
(`f"SELECT ... LIKE '%{q}%'"`), meaning any input containing `'` could break
out of the query. The ICO audit in autumn would have flagged this on sight.

**What:** all four query sites now use parameterised `?` placeholders:

```python
db.execute(
    "SELECT * FROM requests WHERE subject LIKE ? OR requester LIKE ? "
    "ORDER BY deadline",
    (f"%{q}%", f"%{q}%"),
)
```

Wildcards (`%…%`) are added in Python, not SQL, so pattern matching still works
without letting the user break out of the string.

### 2. `SECRET_KEY` and `debug=True` — removed as defaults

**Why:** `secret_key = "dev"` in production means anyone who knows the source
can forge sessions. `debug=True` in production leaks stack traces and exposes
the Werkzeug debugger (RCE risk).

**What:**
- `SECRET_KEY` is now read from the environment. If it's missing, the app
  raises `RuntimeError` at import time — you can't accidentally start it.
- `debug` is opt-in via `FLASK_DEBUG=1` (default off).
- `FOI_DB` env var makes the DB path configurable — used by tests for isolation.

### 3. Single-page app (`foi_tracker/templates/app.html`)

**Why:** the lab serves the app at `/proxy/5002/`. Clicking a row on the old
version tried to open `/request/1`, which resolved to `https://…/request/1`
(missing the proxy prefix) and 404'd. Users literally could not test search
or open a request.

**What:**
- `/` returns one HTML shell with inline JS.
- Data moved behind a JSON API: `GET/POST /api/requests`, `GET/POST /api/requests/<id>`.
- List, new-request form, and detail/edit are panels in the same page, shown
  and hidden via vanilla JS + `fetch()`.
- Fetch URLs are **relative** (`api/requests`, not `/api/…`) and a
  `<base href="./">` in the shell locks the base to the current path.
  The app now works under any URL prefix.
- Old templates (`base.html`, `index.html`, `new.html`, `detail.html`) removed.

### 4. Repo restructured

**Why:** the original layout was a flat pile — `app.py`, `deadlines.py`,
`seed.py`, `test_app.py`, `templates/` all at the root. Hard to navigate,
no separation between app and tests.

**What:**

```
foi_tracker/       Flask app, routes, deadline logic, templates
tests/             Pytest suite (6 tests)
scripts/           seed.py — run with `python -m scripts.seed`
docs/              AI_LOG, TEAM-PLAN, hackathon brief, this PR description
run.py             Entry point
pytest.ini         Test config
```

### 5. Tests (`tests/test_security.py`)

All 6 pass. Run with `python -m pytest`.

| Test | What it proves |
|---|---|
| `test_search_blocks_sql_injection` | `?q=' OR 1=1--` returns `[]` |
| `test_search_returns_matching_row` | Normal search still works |
| `test_new_request_handles_quotes_safely` | Apostrophes in fields insert cleanly |
| `test_update_request_handles_quotes_safely` | Apostrophes in notes update cleanly |
| `test_index_serves_single_page_shell` | `/` returns the SPA shell |
| `test_app_refuses_to_start_without_secret_key` | Startup guard works |

### 6. Docs

- `CLAUDE.md` (root) — project shape, non-negotiable conventions, in-flight work.
- `foi_tracker/CLAUDE.md` — security rules for the app package with do/don't examples.
- `tests/CLAUDE.md` — the fixture pattern.
- `docs/AI_LOG.md` — dated change log.
- `README.md` — trimmed to layout + setup + tests.

---

## How to run locally

```bash
pip install -r requirements.txt
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
python -m scripts.seed
python run.py
```

App: <http://localhost:5002>. For auto-reload: `FLASK_DEBUG=1 python run.py`.

## Out of scope (intentionally)

- Bank-holiday-aware deadlines — Serena, tracked separately.
- Login / auth — Haseeb's follow-up (needed before the audit log).
- Audit log for status changes — Satyavrat, depends on login.
- Backups + GDPR — Teemerte.

---

## Commit trail
```
c363ba4 docs: expand CLAUDE.md with security summary, add PR description
5fb2865 Convert to single-page app so it works behind the lab proxy
b7d384d Tighten README; add CLAUDE.md context files
b6e1d24 Restructure into package layout with tests/, scripts/, docs/
c70f97d Harden app security: parameterise SQL, require SECRET_KEY, disable debug
```
