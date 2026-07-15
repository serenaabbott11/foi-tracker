# Claude context — FOI Deadline Tracker

Small Flask app the DfT central FOI team uses to log requests and compute the
statutory 20-working-day deadline. This will be audited by the ICO in autumn.

**Shape:** single-page app. `/` returns one HTML shell; the browser talks to
`/api/requests[/{id}]` via `fetch()`. This is required because the lab
environment serves the app under a proxy prefix (`/proxy/5002/`), and
server-rendered navigation to `/request/<id>` breaks under that prefix.

## Project structure

```
foi_tracker/    Application package — Flask app, routes, deadline logic, templates
tests/          Pytest suite (run with `python -m pytest`)
scripts/        seed.py — run with `python -m scripts.seed`
docs/           AI_LOG.md (changelog), TEAM-PLAN.txt, hackathon brief
run.py          Entry point
```

## Non-negotiable conventions

- **`SECRET_KEY` must come from the environment.** Never hard-code it, never
  default it. The app raises at startup if it's missing.
- **All SQL uses parameterised queries.** Never build a query with f-strings
  or `%` formatting. See `foi_tracker/CLAUDE.md` for the pattern.
- **`debug=True` is not committed.** Debug is opt-in via `FLASK_DEBUG=1`.
- **Fetch URLs in the frontend are relative** (`api/requests`, not `/api/…`).
  A `<base href="./">` in the shell locks the base to the current path so the
  app works under any URL prefix (e.g. the lab proxy).
- **Templates live in `foi_tracker/templates/`** so Flask finds them via the
  package. There is only one template — `app.html` — the SPA shell.

## What has already been done (fix/security-hardening branch)

1. **SQL injection closed** — four f-string queries in `app.py` (search,
   insert, update, select-by-id) replaced with parameterised queries.
2. **`SECRET_KEY` required** — moved out of source, checked at startup.
3. **`debug=True` removed** — opt-in via `FLASK_DEBUG=1`.
4. **Repo restructured** into `foi_tracker/` / `tests/` / `scripts/` / `docs/`.
5. **Single-page app** — the multi-page version was broken by the lab proxy;
   everything now runs through `/` + `/api/…` with vanilla JS.
6. **Tests added** — six tests in `tests/test_security.py` covering all four
   SQL paths, the SPA shell, and the SECRET_KEY startup check.

## Workflow

- Every change goes on a branch (`fix/…`, `feature/…`, `security/…`).
- Tests must pass (`python -m pytest`) before pushing.
- Add an entry to `docs/AI_LOG.md` for any non-trivial change.
- Team ownership: see `docs/TEAM-PLAN.txt`.

## Currently in flight

- Bank-holiday-aware deadline calculation (Serena) — `foi_tracker/deadlines.py`
- Basic auth / login (Haseeb) — dependency for the audit log
- Audit log for status changes (Satyavrat) — needs login first
- Backup + GDPR + presentations (Teemerte)
