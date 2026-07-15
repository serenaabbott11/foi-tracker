# Claude context — `foi_tracker/` package

This is the Flask app. The ICO will audit it. Two rules matter more than anything else.

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

## Adding new routes

- Import `db.execute` — pass values as a tuple, always. No exceptions.
- Escape any user-controlled data going into templates via Jinja's default
  autoescape — do not use `{% raw %}{{ x | safe }}{% endraw %}` on user input.
- Wrap DB writes in `db.commit()`; wrap reads in nothing.
