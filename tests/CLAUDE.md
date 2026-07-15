# Claude context — `tests/`

Pytest suite. Run with `python -m pytest` from the repo root.

## Fixture pattern

The shared `client` fixture lives in `conftest.py` and:

1. Creates a temp SQLite file and seeds 5 varied rows (`SAMPLE_ROWS`).
2. Sets `SECRET_KEY` and `FOI_DB` via `monkeypatch`.
3. Reloads `foi_tracker.app` so the module re-reads the env vars.
4. Yields a Flask test client.
5. Deletes the temp DB on teardown.

Every test file that needs the app should take `client` as a parameter —
pytest picks it up automatically from `conftest.py`.

`_reload_app()` clears the cached module so tests are independent. Tests
that need to reload the app themselves (e.g. `SECRET_KEY` missing) can
inject the `reload_app` fixture.

## What we test

- `test_security.py` — SQL injection blocked, quotes handled cleanly on
  insert/update, `/` returns the SPA shell, app refuses to start
  without `SECRET_KEY`.
- `test_search.py` — search matches every column, case-insensitive,
  whitespace-trimmed, empty query returns everything, substring
  matches work, no-match returns `[]`.
- `test_deadlines.py` — `calculate_deadline` returns the right date across
  Easter, Christmas, and the Summer bank holiday. Also asserts Maundy
  Thursday counts as a working day (it isn't a UK bank holiday, and
  treating it as one silently slips every Easter-period deadline by a day).
  The Scotland 2nd January case guards the FOI Act s.10(6) requirement
  that a bank holiday in *any* of the four UK nations is a non-working
  day — losing that would under-count deadlines for requests spanning
  Scotland- or NI-specific holidays (2 Jan, St Patrick's, Battle of the
  Boyne, St Andrew's).

## Adding tests

Prefer the `client` fixture. If you need a fresh DB per test, that's already
what the fixture provides — each test gets its own tempfile.

Pure logic tests (like `test_deadlines.py`) skip the fixture entirely — just
`from foi_tracker.deadlines import ...` and assert. The bank-holiday JSON is
loaded at import time from inside the package, so no env setup is needed.

For tests that must run *without* the fixture setting env vars (e.g. asserting
startup failure), use `monkeypatch.delenv(...)` explicitly and call `_reload_app()`.
