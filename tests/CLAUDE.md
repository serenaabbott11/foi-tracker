# Claude context — `tests/`

Pytest suite. Run with `python -m pytest` from the repo root.

## Fixture pattern

Each test that needs the app uses the `client` fixture:

1. Creates a temp SQLite file and seeds one row.
2. Sets `SECRET_KEY` and `FOI_DB` via `monkeypatch`.
3. Reloads `foi_tracker.app` so the module re-reads the env vars.
4. Yields a Flask test client.
5. Deletes the temp DB on teardown.

`_reload_app()` clears the cached module so tests are independent — always call
it before importing `foi_tracker.app` inside a test.

## What we test

- `test_security.py` — every SQL path is parameterised (search, insert, update, select),
  and the app refuses to start without `SECRET_KEY`.

## Adding tests

Prefer the `client` fixture. If you need a fresh DB per test, that's already
what the fixture provides — each test gets its own tempfile.

For tests that must run *without* the fixture setting env vars (e.g. asserting
startup failure), use `monkeypatch.delenv(...)` explicitly and call `_reload_app()`.
