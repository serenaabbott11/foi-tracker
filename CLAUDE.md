# Claude context — FOI Deadline Tracker

Small Flask app the DfT central FOI team uses to log requests and compute the
statutory 20-working-day deadline. This will be audited by the ICO in autumn.

## Project structure

```
foi_tracker/    Application package — routes, deadline logic, templates
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
- **Templates and Flask defaults** — templates live in `foi_tracker/templates/`
  so Flask finds them automatically via the package.

## Workflow

- Every change goes on a branch (`fix/…`, `feature/…`, `security/…`).
- Tests must pass (`python -m pytest`) before pushing.
- Add an entry to `docs/AI_LOG.md` for any non-trivial change.
- Team ownership: see `docs/TEAM-PLAN.txt`.

## Currently in flight

- Bank-holiday-aware deadline calculation (Serena) — `foi_tracker/deadlines.py`
- Audit log for status changes (Satyavrat) — needs login first
- Basic auth / login (Haseeb) — dependency for the audit log
- Backup + GDPR + presentations (Teemerte)
