# FOI Deadline Tracker

Tracks Freedom of Information requests for the DfT central FOI team and
calculates the statutory 20-working-day response deadline.

Single-page app: one HTML shell served at `/`, all data over `/api/requests`.

## Layout

```
foi_tracker/    Flask app, routes, deadline logic, templates
tests/          Pytest suite
scripts/        seed.py — populates foi.db with sample data
docs/           AI_LOG, TEAM-PLAN, hackathon brief
run.py          Entry point
```

## Setup

```bash
pip install -r requirements.txt
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
python -m scripts.seed
python run.py
```

App: <http://localhost:5002>

For dev with auto-reload: `FLASK_DEBUG=1 python run.py`

## Tests

```bash
python -m pytest
```

## Notes

- `SECRET_KEY` is **required** — the app refuses to start without it.
- Deadlines currently exclude weekends only; bank holidays are being added (see [`docs/TEAM-PLAN.txt`](docs/TEAM-PLAN.txt)).
- Changes are logged in [`docs/AI_LOG.md`](docs/AI_LOG.md).
