# FOI Deadline Tracker

Tracks Freedom of Information requests for the DfT central FOI team and
calculates the statutory 20-working-day response deadline.

## Layout

```
foi-tracker/
├── foi_tracker/      Application package (Flask app, routes, deadline logic)
│   └── templates/    HTML templates
├── tests/            Pytest suite
├── scripts/          Utility scripts (seed the DB)
├── docs/             Team plan, AI change log, hackathon brief
├── run.py            Entry point
└── requirements.txt
```

## Running it

```
pip install -r requirements.txt
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
python -m scripts.seed        # creates foi.db with sample data (wipes existing!)
python run.py                 # starts the app on http://localhost:5002
```

For local dev with auto-reload:

```
FLASK_DEBUG=1 python run.py
```

## Running the tests

```
python -m pytest
```

## Notes

- Deadlines: 20 working days from receipt. Bank holidays are **not yet** excluded (see [`docs/TEAM-PLAN.txt`](docs/TEAM-PLAN.txt)).
- `SECRET_KEY` is required; the app refuses to start without one.
- Change log lives in [`docs/AI_LOG.md`](docs/AI_LOG.md).
