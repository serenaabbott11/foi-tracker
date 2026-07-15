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

## Data, backup & restore

The database lives at `data/foi.db` — **outside the code tree**, so editing
code or re-running `seed.py` never sits on top of live data. The `data/`
directory is gitignored (only `.gitkeep` is tracked).

```bash
python -m scripts.backup      # verified snapshot -> data/backups/foi-<timestamp>.db
python -m scripts.restore     # restore the newest backup
python -m scripts.restore data/backups/foi-20260715-141112.db   # a specific one
```

- Backups use SQLite's online backup API, so they are safe to take **while the
  app is running** and are transactionally consistent.
- Each backup is verified with `PRAGMA integrity_check`; a corrupt backup is
  never kept, and `restore` refuses to write one over your live DB.
- `restore` copies the current DB aside to `data/foi.db.pre-restore-<timestamp>`
  first, so a restore is itself reversible.
- The newest `FOI_BACKUP_KEEP` (default 14) backups are retained; older ones
  are pruned automatically.
- Proven by `tests/test_backup_restore.py` (backup → data loss → restore →
  data matches).

For scheduled backups, add a cron entry, e.g. hourly:

```cron
0 * * * * cd /path/to/foi-tracker && python -m scripts.backup >> data/backups/backup.log 2>&1
```

## Notes

- `SECRET_KEY` is **required** — the app refuses to start without it.
- Deadlines currently exclude weekends only; bank holidays are being added (see [`docs/TEAM-PLAN.txt`](docs/TEAM-PLAN.txt)).
- Changes are logged in [`docs/AI_LOG.md`](docs/AI_LOG.md).
