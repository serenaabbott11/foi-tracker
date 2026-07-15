# Claude context — `foi_tracker/` package

This is the Flask app. It's a **single-page app**: `/` returns one HTML shell
(`templates/app.html`), and the browser talks to `/api/requests[/{id}]` via
`fetch()`. All fetch URLs in the template are relative (`api/requests`, not
`/api/…`) so they work under the lab proxy prefix. Do not add server-side
navigation that assumes the app is mounted at `/`.

The ICO will audit it. Two rules matter more than anything else.

## Rule 1 — Every SQL query is parameterised

Use `?` placeholders. Never interpolate user input into a query string. The
prior version used f-strings everywhere and was trivially exploitable.

```python
# YES
db.execute(
    "SELECT * FROM requests WHERE subject LIKE ? OR requester LIKE ?",
    (f"%{q}%", f"%{q}%"),
)

# NO — do not do this
db.execute(f"SELECT * FROM requests WHERE subject LIKE '%{q}%'")
```

The wildcards (`%…%`) are added in Python, not SQL. That keeps the pattern-match
behaviour without letting the user break out of the string literal.

A test in `tests/test_security.py` sends `?q=' OR 1=1--` and asserts nothing
comes back. If a future change breaks parameterisation, that test will fail.

## Rule 2 — `SECRET_KEY` is required, from the environment only

```python
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    raise RuntimeError("SECRET_KEY environment variable must be set")
app.secret_key = _secret
```

Do not add a default. Do not add a dev fallback. Callers must set it explicitly.
This is guarded by `test_app_refuses_to_start_without_secret_key`.

## Config summary

| Env var        | Purpose                                    | Default   |
|----------------|--------------------------------------------|-----------|
| `SECRET_KEY`   | Flask session signing key                  | *required* |
| `FLASK_DEBUG`  | `"1"` turns on Werkzeug debug (dev only)   | off       |
| `FOI_DB`       | Path to the SQLite DB                      | `foi.db`  |

## Adding new endpoints

- Add a JSON endpoint under `/api/…` — the frontend fetches it.
- `db.execute` — pass values as a tuple, always. No exceptions.
- Return `jsonify(...)` for success; use appropriate HTTP status codes
  (`201` for create, `404` for not found).
- Wrap DB writes in `db.commit()`; wrap reads in nothing.

## Frontend

- The whole UI lives in `templates/app.html` (HTML + inline CSS + inline JS).
- Show/hide the `#new-panel` and `#detail-panel` divs via the `hidden` class.
- Escape all user-controlled data going into the DOM with the `esc()` helper.
  Never do `element.innerHTML = userInput` without escaping.
- Keep fetch URLs relative (`api/requests`, `api/requests/${id}`) — the
  `<base href="./">` tag depends on this.
