# Agent Log — FOI Deadline Tracker

This log tracks AI-assisted changes to this repository. It complements git history — see `Claude.md` §"Two Records, Two Jobs".

## Format

Each entry:
- **Date + agent name** (ISO date, `Agent_<name>`)
- **What changed** — files, brief summary
- **Why** — motivation, plan reference
- **Trajectory notes** — only if the work took meaningful iteration or a change of direction; omit for one-shot changes

---

## 2026-07-15 — Agent_Satyavrat

### Session context

- Branch: `operations_GDPR_audit`
- Base: fast-forwarded to `fix/security-hardening` tip (`bdb479f`) via `git merge origin/fix/security-hardening`
- Implementation plan: `plan.md` (git-ignored; local review artefact, not committed)
- Scope: Operations, Data Protection, Audit Logs (see `plan.md` §2–4)

### Reformatted `Claude.md` as markdown

- **Files:** `Claude.md`
- **What:** applied H1/H2/H3 hierarchy, bulleted the list content, wrapped the commit-message example in a fenced code block. Content preserved verbatim — no edits to intent.
- **Why:** user request; the file is meant to be referred to by any agent working on the repo, so it needs to be legible markdown rather than run-together plain text.
- **Observation flagged to user:** `Claude.md` (mixed case) sits alongside the existing `CLAUDE.md` (all caps). On this case-sensitive filesystem they are distinct files. Agents that scan for `CLAUDE.md` will not automatically read `Claude.md`. Options: (a) merge into `CLAUDE.md`; (b) rename to `AGENTS.md`; (c) leave and cross-reference. Awaiting user decision.

### Created `Agent_log.md`

- **Files:** `Agent_log.md` (this file)
- **What:** initial structure and this entry.
- **Why:** user request — log every change with agent name `Agent_Satyavrat`. Also aligns with `Claude.md` §"Two Records, Two Jobs".

### OPS-1 — safe DB default + `seed.py --force` guard

- **Files:**
  - `foi_tracker/app.py` — default DB path is now `<repo>/data/foi.db` (previously `./foi.db`). Overridable via `FOI_DB` env var unchanged.
  - `scripts/seed.py` — refactored top-level script into `seed(db_path, force=False)` + `main(argv)`. Refuses to overwrite an existing DB unless `--force`. Creates parent directory if missing. Adds `--db` flag.
  - `scripts/__init__.py` — new (empty) so `scripts` is an importable package for tests.
  - `data/.gitkeep` — new; keeps the data dir tracked while `*.db` in `.gitignore` continues to ignore DB files inside it.
  - `tests/test_seed_guard.py` — 4 new tests: creates new DB, refuses without `--force`, overwrites with `--force`, creates parent dirs.
- **Why:** `plan.md` OPS-1. Answers the "seed wipes the DB" foot-gun from the current-state audit. Keeps the DB off the code directory by default so an accidental repo checkout/clean can't wipe live data.
- **Verification:** `python -m pytest` → 10/10 green (6 baseline + 4 new). Manual smoke: `python -m scripts.seed` creates `data/foi.db`; second run exits 1 with "already exists" message; `--force` overwrites.
- **Trajectory notes:** one-shot; no rework.

### AUD-1 — audit_log table + immutability triggers + migration

- **Files:**
  - `scripts/migrate_add_audit_log.py` — new. Idempotent migration exposing `apply(conn)` plus a CLI (`python -m scripts.migrate_add_audit_log [--db PATH]`). Uses `CREATE TABLE / TRIGGER / INDEX IF NOT EXISTS` so repeated runs are safe.
  - `scripts/seed.py` — imports `apply_audit_log` and calls it after inserting sample rows, so a fresh seed produces a complete DB (both `requests` and `audit_log`).
  - `tests/test_audit_log_schema.py` — 6 new tests: table + triggers exist after `apply`; `apply` is idempotent (called 3×); INSERT permitted; UPDATE rejected (raises `DatabaseError` matching "audit log is immutable"); DELETE rejected (row remains); `scripts.seed.seed()` produces a DB with both tables.
- **Why:** `plan.md` AUD-1. The ICO auditor will ask "who changed this record?" — this is the storage layer for the answer. Immutability triggers are the tamper-evident guarantee referenced in plan.md AUD-4.
- **Schema choices worth flagging for review:**
  - Kept `before_json` / `after_json` as TEXT columns holding JSON (rather than separate before/after columns per field) so the schema stays stable as the `requests` table grows (`retention_until`, `team_id`, etc. from DP-1 / DP-4).
  - Added two indexes not in the original plan spec: `(entity_type, entity_id)` for "history of request X" queries, and `(timestamp)` for date-range scans in the AUD-5 viewer. Cheap, kept small.
  - Triggers use `RAISE(ABORT, ...)` which in Python surfaces as `sqlite3.DatabaseError` with the message "audit log is immutable" — tested.
- **Verification:** `python -m pytest` → 16/16 green (10 previous + 6 new). Manual smoke: ran the migration against `data/foi.db`, verified `.schema audit_log`, confirmed CLI UPDATE rejected with `Error: stepping, audit log is immutable (19)`. Re-seeded to clear the smoke-test row; `audit_log` now empty and ready for AUD-2.
- **Trajectory notes:** one-shot; no rework.

### AUD-2 — audit write path (actor='unknown' pending AUD-3)

- **Files:**
  - `foi_tracker/audit.py` — new. `write_audit(conn, *, action, entity_type, entity_id, actor='unknown', actor_ip, before, after, reason)`. INSERT only — does not commit; caller owns the transaction, so the audit row lands atomically with the caller's change.
  - `foi_tracker/app.py` — instrumented all four API endpoints:
    - `POST /api/requests` → logs `create` with `after={ref, requester, subject, received, deadline, status}`.
    - `GET /api/requests/<id>` → logs `view` (no before/after; the fact of access is the payload).
    - `POST /api/requests/<id>` → fetches the row first, logs `update` with `before={status, notes}` and `after={status, notes}`. **Behaviour change:** now returns 404 if the row doesn't exist (was previously a silent no-op that returned 200).
    - `GET /api/requests` (list) → **deliberately NOT logged.** Rationale: list reads are noisy and reveal nothing sensitive per-item beyond what a `view` on each row would; per-row visibility comes from the `view` action.
    - Introduced module-level `_ACTOR_UNKNOWN = "unknown"` sentinel — AUD-3 will swap this for `current_user.username` in one place.
  - `tests/test_security.py` — fixture now also runs `apply_audit_log(conn)` so endpoints (which write to `audit_log`) work under test.
  - `tests/test_audit_write.py` — new. 7 tests: create writes row; view writes row; update writes row with before+after JSON; update on missing row → 404 + no audit; list writes nothing; view on missing row → 404 + no audit; `actor_ip` is `127.0.0.1` under the test client.
- **Why:** `plan.md` AUD-2. This is the "who did what to which record" the ICO auditor will ask for.
- **Verification:**
  - Unit: `python -m pytest` → 23/23 green (16 previous + 7 new).
  - End-to-end: seeded a real DB, started `python run.py`, created request 14 via `curl`, viewed it, updated it. `sqlite3` inspection of `audit_log` shows three rows with correct action, entity_id, actor='unknown', actor_ip='127.0.0.1', UTC timestamps, and correct before/after JSON on the update.
- **Trajectory notes:** one-shot; no rework. Small behaviour change (silent no-op → 404 on missing `POST /api/requests/<id>`) was necessary for the audit's "before" state to be meaningful — flagged for the team.

---

## Pause point — checking in with user

Day 1 items 1–3 from `plan.md` §5 are done: OPS-1, AUD-1, AUD-2.
Remaining Day 1: OPS-3 (backups + restore drill) and DP-1 (retention columns).
Nothing has been committed yet — awaiting user sign-off on the code before making the first `[Agent_Satyavrat]` commit(s).
