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

### Committed OPS-1 / AUD-1 / AUD-2, merged origin/main, pushed branch

- **Commits:**
  - `e260b2b` — docs: merge workflow rules into CLAUDE.md; add Agent_log
  - `39bdc85` — OPS-1: safe DB default + seed.py --force guard
  - `df92b27` — AUD-1: audit_log table + immutability triggers
  - `d314295` — AUD-2: audit write path (actor='unknown' pending AUD-3)
  - `81969a9` — Merge origin/main (Serena's PR #4: bank-holiday deadline fix)
- **Why split into four commits:** followed `CLAUDE.md` §"Commit message example". Each of the three code commits touches only its own concern — used intermediate file rewrites of `foi_tracker/app.py` and `scripts/seed.py` so the OPS-1 commit doesn't carry AUD-2 hunks and vice versa. Clean per-feature `git log --stat` / `git blame`.
- **Merge context:** `origin/main` moved forward while we were working. Merged in Serena's bank-holiday fix (`foi_tracker/deadlines.py`, `foi_tracker/bank-holidays.json`, `tests/test_deadlines.py`, `tests/CLAUDE.md`). No conflicts — she touched files we didn't. `calculate_deadline` signature unchanged, so our seed/app code still works.
- **Push:** `git push -u origin operations_GDPR_audit` — remote branch created. Team can now checkout and test.
- **Verification:** `python -m pytest` at HEAD → 28/28 green (23 ours + 5 from Serena's deadline tests).
- **Trajectory notes:** one item worth flagging — I had to configure `git config user.name` / `user.email` locally (repo-scoped, not `--global`) because git wouldn't let me commit without an identity; asked user for the values first per system rules.

---

## Pause point cleared — continuing with plan.md Day 1 §4–5

Next: OPS-3 (backup + restore + drill), then DP-1 (retention columns).

### OPS-3 — backup + restore + drill runbook

- **Files:**
  - `scripts/backup.sh` — new. Uses `sqlite3 .backup` (SQLite's online backup API, safe on a live DB), gzips into `$BACKUP_DIR`, prunes to the 14 most recent by mtime. Writes an `action='backup'`, `actor='system'` row to `audit_log`. Best-effort audit — missing `audit_log` table only warns, doesn't fail the backup.
  - `scripts/restore.sh` — new. Takes a `.db.gz` path. Extracts to a same-filesystem staging path (so the final `mv` is atomic), smoke-tests that `requests` and `audit_log` both query cleanly, moves the current live DB aside as a `.pre-restore-<ts>` safety copy, swaps the restored DB in, writes an `action='restore'` audit row to the restored DB.
  - `docs/RESTORE-DRILL.md` — new. The runbook for "Gary's machine dies on a Wednesday", including a **drill log table** to be filled in on the first real rehearsal. Explicitly documents one known limitation (§4): the `action='backup'` audit row is written *after* the snapshot, so it never appears inside the backup it describes — the backup file itself is the durable evidence.
  - `tests/test_backup_restore.py` — new. 7 subprocess-driven tests: backup produces `.db.gz`; backup writes audit row; end-to-end round-trip (baseline count → backup → delete DB → restore → count matches); restore writes audit row; restore rejects a corrupt `.db.gz`; restore errors on missing file; retention keeps only the 14 most recent files.
  - `.gitignore` — added `backups/` and `data/foi.db.pre-restore-*` so drill artefacts don't accidentally get committed.
- **Why:** `plan.md` OPS-3. Highest-value operations item — this is the answer to the ICO auditor's Q4 (*"Gary's machine dies, walk me through recovery"*).
- **Design choices worth noting:**
  - Retention is **daily-only automatic** (14 files). Weekly (8-week retention) is documented as a *manual promotion* step in `RESTORE-DRILL.md`. Rationale: automatic weekly tagging needs either a separate cron or in-script day-of-week logic, both of which add moving parts. Manual promotion is honest.
  - Backup filenames use **UTC** timestamps (`foi-YYYYMMDD-HHMMSSZ.db.gz`) — hosts across time zones sort consistently.
  - Staging paths sit on the **same filesystem** as their target so the final `mv` is atomic (no torn state if the process is killed).
  - Restore does an active **smoke test** on the staging DB before touching the live one — a corrupted backup can't nuke a healthy live DB.
- **Verification:**
  - Unit: `python -m pytest` → 35/35 green (28 previous + 7 new).
  - Manual smoke: seeded → backup → verified `.db.gz` in `backups/` → deleted `data/foi.db` → ran `restore.sh` → verified `requests` count matches, audit row for restore present.
- **Trajectory notes:** one-shot; no rework.

### DP-1 — retention columns migration + write path

- **Files:**
  - `scripts/migrate_add_retention.py` — new. Idempotent migration exposing `apply(conn)` + CLI. Uses `PRAGMA table_info` to detect which columns exist before running each `ALTER TABLE ADD COLUMN`. Adds five columns: `created_at`, `updated_at`, `responded_at`, `retention_until`, `team_id`. Backfills for existing rows: `created_at`/`updated_at` from `received`; `responded_at` from `received` **only** when `status='Responded'`; `retention_until` and `team_id` left NULL (populated by DP-3 sweeper and DP-4 team-scoping later).
  - `scripts/seed.py` — imports and calls `apply_retention(conn)` after `apply_audit_log(conn)`, so a fresh `python -m scripts.seed` produces a DB with all columns from the outset.
  - `foi_tracker/app.py`:
    - `POST /api/requests`: INSERT now populates `created_at` and `updated_at` with `now_utc_iso()`.
    - `POST /api/requests/<id>`: UPDATE bumps `updated_at`; uses a SQL `CASE` expression to set `responded_at` **only on the transition** to `'Responded'` and **only if it isn't already set** — re-saving a Responded row does not reset the responded date.
    - Imports `now_utc_iso` from `foi_tracker.audit` (reused, one canonical timestamp helper).
  - `tests/test_security.py`, `tests/test_audit_write.py`, `tests/test_backup_restore.py` — each fixture now calls `apply_retention(conn)` alongside `apply_audit_log(conn)`, so existing tests keep passing after the schema change.
  - `tests/test_retention_schema.py` — new. 9 tests: migration adds all columns; idempotent (3×); backfills `created_at`/`updated_at` from `received`; backfills `responded_at` only when status is Responded; missing `requests` table → RuntimeError; `POST /api/requests` sets timestamps; `POST /api/requests/<id>` bumps `updated_at` without touching `created_at`; transition to Responded sets `responded_at`; re-saving Responded does not clobber `responded_at`.
- **Why:** `plan.md` DP-1. Foundation for DP-3 (retention sweeper) — the sweeper needs `responded_at` and `retention_until` to know which rows are due for PII scrubbing. Also foundation for DP-4 (team separation) via `team_id`.
- **Design choices:**
  - `responded_at` is set with a `CASE` in the same UPDATE, atomic — no separate SELECT / UPDATE race.
  - Timestamps are ISO-8601 UTC with `Z` suffix, second precision — matches the audit_log convention.
  - Retention columns are TEXT (matching how other date columns are stored). Using ISO-8601 strings keeps the whole schema string-comparable and human-readable.
- **Verification:**
  - Unit: `python -m pytest` → 44/44 green (35 previous + 9 new).
  - Manual smoke: seeded fresh DB, confirmed backfilled `created_at`/`updated_at`/`responded_at` on the sample rows (Responded rows have all three, in-progress rows have `responded_at` NULL). Live-created row via curl POST + status transition to Responded → all three timestamps populated with the same UTC ISO instant.
- **Trajectory notes:** the first smoke-test attempt showed the new row with NULL timestamps; turned out a stray `python run.py` process was still bound to :5002 from an earlier session and answered the curl before the freshly-started server did. Killed the stale process, retried, all correct. Not a code bug — an environment gotcha worth remembering when smoke-testing.

### Merge origin/main — PR #5 (Serena's search improvements)

- **Commit:** `b9cced6`
- **Brought in:** case-insensitive `LOWER()` search across a `SEARCHABLE_COLUMNS` allowlist, whitespace-trimmed query, UI polish (shorter placeholder, status autocomplete), and a new `tests/conftest.py` centralising the `client` and `reload_app` fixtures.
- **Manual conflict resolution:** `tests/test_security.py` had two competing rewrites — origin/main deleted the inline `client` fixture (moved to `conftest.py`), while our branch had extended it with `apply_audit_log` + `apply_retention`. Took origin/main's slim `test_security.py`, moved the migration hooks into `conftest.py`'s `client` fixture instead — so every test now uses the shared fixture *and* gets audit_log + retention columns.
- **Verification:** 57/57 tests pass at the merge tip (44 ours + 13 from PR #5).
- **Trajectory notes:** the two-way rewrite of the fixture was the interesting bit. Adopting `conftest.py` as the single source of test-DB shape is the right call anyway — reduces the fixture drift risk across `test_audit_write.py`, `test_backup_restore.py`, etc. Those still have their own fixtures for now (out of scope for this merge).

### OPS-6 — healthcheck `GET /api/healthz`

- **Files:**
  - `foi_tracker/app.py` — added `healthz()` handler. Returns `200 {"ok": true, "db": true}` when `SELECT 1` succeeds on `get_db()`; `503 {"ok": false, "db": false}` on `sqlite3.Error`. Deliberately **not** audit-logged — cron / Docker HEALTHCHECK will hammer this endpoint and it would flood `audit_log`.
  - `tests/test_healthz.py` — 2 tests. Endpoint returns `{ok: true, db: true}` under the normal fixture; three sequential hits produce zero audit rows.
- **Why:** `plan.md` OPS-6. Cheap dependency for OPS-4a's `HEALTHCHECK` directive in the Dockerfile, and for any external monitor. Auth-free by design (needs to work before login lands).
- **Verification:** `python -m pytest` → 59/59 green.
- **Trajectory notes:** one-shot; no rework.

### OPS-4 — Dockerfile + docker-compose + install.sh + systemd units

The full "deployment story that isn't Gary's desktop." Both paths from
the brief (container *and* setup script) are shipped, per user decision.

- **Files:**
  - `Dockerfile` — new. `python:3.12-slim` base + `sqlite3` CLI (needed by `backup.sh`/`restore.sh`). Non-root `foi` user. Gunicorn (`--workers 2`, access + error logs to stdout). Data + backups in named volumes (`/data`, `/backups`) with `FOI_DB` / `BACKUP_DIR` env vars pointed at them. `HEALTHCHECK` probes `/api/healthz` via a `urllib.request` one-liner (no `curl` needed in the image).
  - `docker-compose.yml` — new. `services.app` with the same env, volumes, and a container-level `healthcheck` mirroring the Dockerfile. `SECRET_KEY:?` bail-out if the caller forgot to copy `.env.example` to `.env`.
  - `.env.example` — new. Placeholder `SECRET_KEY=CHANGE_ME` and inline instructions for generating a real one.
  - `deploy/systemd/foi-tracker.service` — new. `Type=exec` under the `foi-tracker` user, Gunicorn, `EnvironmentFile=/etc/foi-tracker/env`, `Restart=on-failure`, and standard hardening (`NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ReadWritePaths` only for `/var/lib/foi-tracker` and `/var/log/foi-tracker`).
  - `deploy/systemd/foi-tracker-backup.service` — one-shot unit that invokes `scripts/backup.sh` under the service user with the same hardening.
  - `deploy/systemd/foi-tracker-backup.timer` — daily at 02:00 local, `Persistent=true` so a missed run catches up on next boot, `RandomizedDelaySec=15min` to stagger multiple hosts.
  - `scripts/install.sh` — new, idempotent installer. Creates `foi-tracker` system user, lays out `/opt/foi-tracker` (code), `/var/lib/foi-tracker` (data + `backups/`), `/var/log/foi-tracker`, generates `SECRET_KEY` on first run into `/etc/foi-tracker/env` (`chmod 600`), seeds a fresh DB or applies the audit_log + retention migrations on upgrades, installs and enables the systemd units. Safe to re-run for upgrades.
  - `docs/DEPLOYMENT.md` — new. Side-by-side runbook: path A (Docker) vs path B (systemd), including manual backup/restore under Docker, log locations, upgrade flow, and an explicit "not doing (and why)" section referencing OPS-8 for aspirational IaC.
  - `requirements.txt` — added `gunicorn` (used in both container and systemd deployments).
  - `tests/test_deploy_artefacts.py` — new, 9 cheap static-validation tests. `bash -n` syntax check on the three shell scripts; Dockerfile mentions `HEALTHCHECK`, `/api/healthz`, `USER foi`, `gunicorn`; docker-compose parses as YAML with the `app` service; systemd units parse as INI with `EnvironmentFile`, `gunicorn`, hardening directives, and `OnCalendar=`; `.env.example` has `SECRET_KEY=CHANGE_ME`.
- **Why:** `plan.md` OPS-4a + OPS-4b. The brief explicitly requires both — container *where possible*, install script *where not*. Both share the same code, env, backup/restore scripts, and the OPS-6 healthcheck; a monitoring probe or auditor can inspect either the same way.
- **Design choices:**
  - Gunicorn (not the Flask dev server) in both paths — matches GDS Way, and `debug=True` remains impossible outside `FLASK_DEBUG=1`.
  - Non-root at runtime in both paths.
  - Hardening on the systemd unit uses only the directives that make sense for a SQLite-backed app; nothing fancy like Landlock or seccomp filters (which need per-distro work).
  - The container HEALTHCHECK deliberately uses a Python one-liner rather than `curl` — no extra apt install, keeps the image slim.
  - `install.sh` **regenerates the venv** on every run rather than trying to upgrade in place. Cheap on this size of app; guarantees a clean install of Gunicorn on upgrades.
- **Verification:**
  - Unit: `python -m pytest` → 68/68 green (59 previous + 9 new).
  - Manual smoke: not run — Docker isn't available on this machine and `install.sh` needs root on a Debian/Ubuntu host. Static validation covers what we can automate; end-to-end is a manual drill described in `docs/DEPLOYMENT.md`.
- **Trajectory notes:** one-shot; no rework.

### OPS-5 — structured logging

- **Files:**
  - `foi_tracker/logging_config.py` — new. `setup_logging(log_dir=..., log_level=...)` configures the `foi_tracker` logger. Always writes to stdout (container-friendly). If `LOG_DIR` is set, additionally writes to `<LOG_DIR>/app.log` under a `RotatingFileHandler` (10 MB × 5 files). Adds a `_RequestIDFilter` that pulls `g.request_id` from Flask when there's a request context, else `"-"`. `new_request_id()` returns an 8-char hex id used per HTTP request. `setup_logging` is idempotent (guards against re-import in tests).
  - `foi_tracker/app.py` — calls `setup_logging(...)` at import time using `LOG_DIR` / `LOG_LEVEL` env vars. Adds a `before_request` handler that stamps `g.request_id = new_request_id()` on every request. Logs one startup message (`FOI Deadline Tracker starting, db=<path>`). `healthz()`'s DB failure path now `logger.warning`s with the exception detail.
  - `tests/test_logging.py` — new, 5 tests. `new_request_id` returns short unique hex ids; `_RequestIDFilter` defaults to `"-"` outside a request; `setup_logging` is idempotent under repeated calls; the concrete format string produces the expected `<ts> LEVEL <logger> [<request_id>] <message>` shape; inside a Flask request context the filter picks up `g.request_id`.
- **Why:** `plan.md` OPS-5. Separate from `audit_log` — this is *ops* logging (startup, errors, warnings). Auditors get audit_log; on-call gets `logging`. Per-request correlation id lets you tie together log lines from the same HTTP request across multiple modules once we log more.
- **Design choices:**
  - **`foi_tracker` logger, not root.** Root is left alone so unrelated libraries don't inherit our formatter. `propagate=False` on `foi_tracker` prevents duplicate lines if the root ever grows a handler.
  - **stdout by default.** Twelve-factor / container-friendly. File handler only when `LOG_DIR` is set (which the systemd unit does; the Docker path doesn't need it).
  - **UTC, Z-suffixed timestamps.** Same convention as `audit_log` — one time convention to reason about.
  - **8-char request id.** Enough for a hackathon; 16-char if we start seeing collisions in prod.
- **Verification:**
  - Unit: `python -m pytest` → 73/73 green.
  - Live smoke: `SECRET_KEY=smoke python run.py` produces the expected startup line:
    ```
    2026-07-15T16:30:52Z INFO foi_tracker.app [-] FOI Deadline Tracker starting, db=/.../data/foi.db
    ```
    The `[-]` is correct — startup happens outside a request context.
- **Trajectory notes:** first live-smoke attempt showed only Werkzeug's dev-server output because a stale `python run.py` from an earlier DP-1 test was still holding port 5002 (that older process didn't have OPS-5's `setup_logging`). Killed it, restarted, saw the startup line — same stale-server pattern noted under DP-1. Worth wrapping smoke tests in a helper that kills any prior server on the port before starting.

### DP-7 — RETENTION, PRIVACY, and DPIA policies

- **Files:**
  - `docs/RETENTION-POLICY.md` — new. Owner + review cadence, inventory of personal data held, lawful basis, a per-field retention schedule table (requests-PII 3y, requests-record 6y, audit_log 6y with content-redaction after that, backups 14 daily + weekly manual promotion), how the DP-3 sweeper will work end-to-end, manual erasure workflow while DP-2 is pending auth, honesty about backup retention vs UK-GDPR "reasonable steps", open questions for the FOI officer.
  - `docs/PRIVACY-NOTICE.md` — new, requester-facing. Controller, why we hold data, what we hold in a table, lawful basis, retention in plain terms, who sees the data inside DfT, rights (including what a right-to-erasure request will actually do), security posture, ICO complaint route.
  - `docs/DPIA.md` — new. ICO-format Data Protection Impact Assessment. Nature/scope/context/purpose, necessity+proportionality, data flow diagram, a **10-risk register** with likelihood/impact/mitigation/residual columns keyed to plan items (R1 unauthorised internal access → AUD-3/DP-4; R2 SQL injection → closed; R3 free-text PII paste; R4 backup theft → DP-6; R5 audit tampering → closed with triggers; R6 disk failure → OPS-3; R7 Gary's desk → OPS-4; R8 SECRET_KEY → closed; R9 cross-team leakage → DP-4; R10 right-to-erasure → DP-2), consultation notes, sign-off placeholders, review cadence.
- **Why:** `plan.md` DP-7. Auditor gold — the ICO reviewer wants to see the policies alongside the code, and having them under `docs/` (versioned with the code, not on a random SharePoint) is the point.
- **Design choices:**
  - Explicitly marked **draft / pending DPO sign-off** on all three. Not overclaiming.
  - Numbers throughout (3y PII, 6y record, 14 daily backups) are called out as *proposed* — the FOI officer needs to confirm departmental practice. Better to flag than to invent authority.
  - The risk register in DPIA §4 maps directly to `plan.md` items so an auditor can trace policy → code without a middle layer.
- **Verification:** doc-only. `python -m pytest` → still 73/73 green.
- **Trajectory notes:** one-shot; no rework. Left a couple of `**[to be confirmed]**` markers where a real department would fill in DPO email etc.

### AUD-5 — audit viewer API + CSV export + SPA History panel

- **Files:**
  - `foi_tracker/app.py` — three new endpoints:
    - `GET /api/requests/<id>/audit` — returns the audit history for one request, newest first, 404 if the request doesn't exist. Returns `entity_type`/`entity_id` alongside `before_json`/`after_json` for consumers that need them.
    - `GET /api/audit` — cross-request view. Supports `?action=`, `?actor=`, `?entity_type=`, `?entity_id=`, `?from=`, `?to=`, `?limit=` filters. Filter column names are an **allowlist** so the f-string composition is safe; values are always parameterised. Result limit clamped to `1000` and gracefully ignores a bad `limit=notanumber`.
    - `GET /api/audit.csv` — same filtering, streams the same rows as RFC-4180 CSV, timestamped `attachment; filename="audit-YYYYMMDDZ.csv"`.
    - Both cross-request endpoints carry a `TODO(AUD-3 / DP-4)` comment: restrict to admin / foi_officer once auth lands.
  - `foi_tracker/templates/app.html` — added a **History** panel:
    - New `View history` button on the detail panel (secondary style, no colour conflict with Save).
    - New `#history-panel` div with a table (When | Who | Action | Change).
    - `showHistory(id, ref)` fetches `api/requests/${id}/audit` and renders rows through `esc()` for every field per `foi_tracker/CLAUDE.md` §"Rule 3".
    - `renderChange(r)` produces a human diff for `update` rows (`<strong>notes</strong>: ∅ → hello`) and short labels for `view`, `create`, and other actions. Null/empty values render as `∅` for clarity.
  - `tests/test_audit_viewer.py` — 12 new tests. Per-request endpoint returns only that request's rows; ordered newest first; 404 for missing requests; before/after diff survives to the API. Cross-request endpoint returns recent rows in DESC order; filters by action; filters by entity; caps overly-large `limit`; tolerates a garbage `limit`. CSV endpoint returns the right MIME type + attachment header + 10 expected columns; filter applies to CSV output; **CSV round-trip preserves a payload containing both commas and quotes** (parsed via `json.loads` to defeat the JSON `\"` escaping — reliable equality check, not substring).
- **Why:** `plan.md` AUD-5. Concrete answer to the ICO's "who accessed this record?" question: caseworker opens a request → clicks *View history* → sees every view/update, timestamped, with a plain-English diff. CSV export is the auditor's takeaway.
- **Design choices:**
  - Filter columns are a hardcoded **allowlist dict** (`_AUDIT_FILTER_COLUMNS`), never user input, so composing `WHERE col = ?` via f-string is safe. Values are always `?`-parameterised.
  - CSV column order is fixed and stable so a downstream spreadsheet reader doesn't break when we add columns later.
  - No pagination on `/api/audit` yet — a hard `LIMIT 1000` clamp is enough for the scale we're at. Full pagination is a Day-3 item.
  - History panel uses **`esc()` on every DOM write**. `renderChange` composes small HTML fragments (`<strong>…</strong>`) but only around already-escaped values — never inserts un-escaped user data into innerHTML.
- **Verification:**
  - Unit: `python -m pytest` → 85/85 green (73 previous + 12 new).
  - The two-step fix: initial run flagged that the per-request endpoint didn't `SELECT entity_id` (KeyError in the test); the CSV special-character test was doing a naive substring lookup on a JSON-escaped string (`\"`). Fixed by selecting the extra columns and by json-parsing the CSV cell before comparison.
- **Trajectory notes:** one iteration. Endpoints landed clean; test failures diagnosed and fixed in one pass each.

### OPS-7 — minimal CI (GitHub Actions)

- **Files:**
  - `.github/workflows/ci.yml` — new. Two jobs on every push and every PR to main:
    - `test` — checkout, setup Python 3.12 with pip cache, `pip install -r requirements.txt`, `python -m pytest -v`. Passes a placeholder `SECRET_KEY` env because `foi_tracker.app` refuses to import without one (tests set their own via monkeypatch, but the module-level guard fires at import time regardless).
    - `security` — same Python setup, `pip install bandit`, `bandit -r foi_tracker/ scripts/ -ll`. `-ll` reports medium+ severity only.
  - `foi_tracker/app.py` — added three `# nosec B608` comments with a written rationale on the three f-string SQL sites:
    - `list_requests` (Serena's search — `WHERE {where}` where `where` is composed from `SEARCHABLE_COLUMNS`, a hardcoded tuple);
    - `audit_index` and `audit_csv` (both use `_audit_query()`, which composes `WHERE` only from `_AUDIT_FILTER_COLUMNS.values()` — hardcoded allowlist). All user values go through `?` binds.
- **Why:** `plan.md` OPS-7. Cheap now that pytest works. Every push proves tests pass and no obvious CWEs.
- **Design choices:**
  - **No deploy step.** Deploying to a real target needs cloud approvals we don't have (see `docs/DEPLOYMENT.md` §"Not doing" and OPS-8's aspirational sketches).
  - **`bandit -ll`** filters to medium+ severity. Low-severity lint (e.g. `assert` in tests) is noise for a hackathon repo.
  - **Suppressed with rationale, not silenced globally.** Three specific `# nosec B608` comments with a written justification, so reviewers can verify. Zero unsuppressed findings.
- **Verification:**
  - Local: `bandit -r foi_tracker/ scripts/ -ll` → `No issues identified.` (3 skipped via `#nosec`).
  - Unit: `python -m pytest` → 85/85 green.
  - **CI itself not yet run** — the workflow lives in `.github/workflows/`; will fire on the next push to origin.
- **Trajectory notes:** bandit initially flagged the three f-string SQL sites. All three are provably safe (allowlist composition + `?`-bound values), but bandit doesn't do taint analysis. Adding `# nosec B608` with a written comment is the accepted practice — reviewers can check the rationale is sound.

### OPS-8 — aspirational Kubernetes + Terraform artefacts

- **Files:**
  - `deploy/README.md` — new landing page pointing at the three sub-dirs (real `systemd/` vs demonstrative `k8s/` and `terraform/`), tagged with a status column.
  - `deploy/k8s/README.md` — new. Prominent ⚠️ disclaimer. Table of what's in the directory. A **What's missing** section (ingress + TLS, real secret management, backup CronJob, monitoring, NetworkPolicy, resource limits, PDB). A **Why we would not pick K8s for this workload today** section — 6–20 users, SQLite single-writer, GDS-Way anti-overprovisioning.
  - `deploy/k8s/deployment.yaml`, `service.yaml`, `configmap.yaml`, `pvc.yaml` — minimal manifests. `Recreate` strategy (SQLite is single-writer, no rolling), `runAsNonRoot`, `readinessProbe`+`livenessProbe` on `/api/healthz`, conservative CPU/mem requests/limits, two PVCs (data + backups) both `ReadWriteOnce`.
  - `deploy/k8s/secret.yaml.example` — placeholder Secret with `PGJhc2U2NC1lbmNvZGVkLXNlY3JldC1oZXJlPg==` (base64 of "<base64-encoded-secret-here>"). Header instructs how to generate a real key and warns against committing the resulting `secret.yaml`.
  - `deploy/terraform/README.md` — parallel ⚠️ disclaimer + What's-missing + Why-not-yet sections.
  - `deploy/terraform/main.tf` — single-VM AWS sketch: `aws_vpc` data source (falls back to default), `aws_security_group`, `aws_s3_bucket` + `versioning` + `public_access_block` + `lifecycle_configuration` (14d daily + 8w weekly), IAM role scoped **only** to the backup bucket, EC2 t3.small on Debian, encrypted `aws_ebs_volume` gp3, optional Route 53 A record.
  - `deploy/terraform/variables.tf` — 8 vars with `default = null` where optional; region defaults to `eu-west-2` (London — most likely for DfT).
  - `deploy/terraform/outputs.tf` — instance IP, backups bucket name, DNS FQDN (null if no zone provided).
  - `tests/test_deploy_aspirational.py` — 19 new tests. All files exist; top README references all three sub-dirs; **every artefact contains the word "aspirational" case-insensitively** (parametrised across all 10 files); K8s YAML parses as valid k8s docs with a `kind`; deployment probes `/api/healthz` + has `runAsNonRoot` + `readinessProbe` + `livenessProbe` + `Recreate`; Terraform main declares the expected resources; S3 bucket blocks public access; `secret.yaml.example` does not accidentally contain a real 64-hex key (regex check ignoring comment lines).
- **Why:** `plan.md` OPS-8. The Day 2 presentation and the ICO audit both benefit from us being able to say "here is where we'd take this next" — but only if the artefacts are labelled honestly as *not yet deployed*.
- **Design choices:**
  - **Disclaimer on every file, not just READMEs.** So a future reader who opens `main.tf` directly (grep, IDE) still sees the "not applied" warning before they try `terraform apply`.
  - **K8s manifests use `Recreate`, not `RollingUpdate`.** SQLite is single-writer; two pods can't share the DB safely. Documented in the deployment.yaml comment.
  - **Terraform IAM role has one policy: write the backup bucket.** No `AdministratorAccess`, no `*:*` — the aspirational sketch should still model least-privilege.
  - **`aws_s3_bucket_public_access_block`** included from the start — a common oversight in tutorial examples that leaks buckets publicly.
  - **A test enforces the disclaimer.** If a future PR adds an artefact without the "aspirational" marker, the test fails.
- **Verification:** `python -m pytest` → 104/104 green (85 previous + 19 new).
- **Trajectory notes:** one-shot; no rework. Initial disclaimer-audit `grep -L "Aspirational"` flagged the two READMEs as missing — false positive because grep was case-sensitive and the READMEs use lowercase in their h1s. Fixed the check with `-i` and the test uses `.lower()` so it can't recur.

---

## 2026-07-16 — Agent_Satyavrat, branch `add_auth`

### Auth: users table, login/logout, endpoint protection, AUD-3 flip, log integration

The largest single change so far — it closes the three plan items that were blocked on Haseeb's login (AUD-3, DP-2 prerequisite, DP-4 prerequisite). Login itself hadn't landed from Haseeb, so we're implementing it here on `add_auth` off `main`.

- **New files:**
  - `scripts/migrate_add_users.py` — idempotent migration. `users` table with `id, username UNIQUE, password_hash, role DEFAULT 'caseworker', team_id, created_at, updated_at` + a `username` index. Roles: `admin | foi_officer | caseworker`.
  - `foi_tracker/auth.py` — `User(UserMixin)` model with `is_admin` / `is_foi_officer` properties, `LoginManager` (login_view=`login`), `init_login(app, get_db)` that registers the user_loader + an unauthorized_handler that returns **`401 JSON` for `/api/...`** and **redirects to `/login` otherwise**. Also `authenticate(conn, u, p)` using `werkzeug.security.check_password_hash`, `hash_password(p)`, and `current_actor()` (returns `current_user.username` when authed, `'anonymous'` when not, `'system'` outside a request context).
  - `foi_tracker/templates/login.html` — minimal GDS-styled sign-in form. POSTs to `login_post` with an `error` slot and a `next` hidden field. Access-audit disclaimer in the hint.
  - `scripts/create_user.py` — CLI for real user creation. Prompts for password interactively via `getpass` (never in shell history), confirms, validates role. Argparse for `--username`, `--role`, `--team-id`, `--db`.
  - `tests/test_auth.py` — **20 new tests** covering endpoint protection (7 endpoints: 4 API paths return 401 JSON, `/api/healthz` stays open, `/` redirects to `/login`); login form renders; already-authed user hitting `/login` bounces to `/`; success sets the session and grants API access; success/failure both write the right `audit_log` action; failure messages do not disclose which field was wrong (same body, either case); `next=` refuses to redirect off-site (`//evil.example.com` → `/`); logout clears the session and audits; logout requires being logged in.

- **Modified files:**
  - `foi_tracker/app.py` —
    - Imports flask-login (`current_user`, `login_required`, `login_user`, `logout_user`) and our auth module.
    - `init_login(app, get_db)` wired in *after* `get_db` is defined so the user_loader has its dependency.
    - `SESSION_COOKIE_SAMESITE='Lax'` + `SESSION_COOKIE_HTTPONLY=True` for baseline session hardening (CSRF-token add is a later hardening pass).
    - **`@login_required` on `/`, `/api/requests` (both verbs), `/api/requests/<id>` (both verbs), `/api/requests/<id>/audit`, `/api/audit`, `/api/audit.csv`.**
    - `/api/healthz` deliberately **not** login-required (container probes / external monitors need it).
    - AUD-3 flip: **removed the `_ACTOR_UNKNOWN = "unknown"` sentinel** and replaced all three `write_audit(..., actor=_ACTOR_UNKNOWN, ...)` sites with `actor=current_actor()`. The comment referencing "sentinel until HASEEB's login lands" is gone.
    - New routes: `GET /login` (renders form, bounces to `/` if already authed), `POST /login` (authenticate → `login_user()` on success + `action='login'` audit, else `action='login_failed'` audit with attempted-username in `reason`; both cases with `actor_ip=request.remote_addr`), `POST /logout` (`login_required`; audits `action='logout'`, then `logout_user()`). `_safe_next()` helper rejects `//foo` and `scheme://foo` targets.
  - `foi_tracker/logging_config.py` — `_RequestIDFilter` now also sets `record.user` from `current_user.username` when authenticated, `'anonymous'` when not, `'-'` outside a request context. `LOG_FORMAT` bumped to `... [%(request_id)s %(user)s] %(message)s`. Every log line now carries who did it.
  - `foi_tracker/templates/app.html` — header adds a **"Signed in as \<username\>"** display and a **Log out** POST-form button, both after the "+ New request" button; CSS additions for the header/user styling.
  - `scripts/seed.py` — imports `apply_users` + `hash_password` + `now_utc_iso`; calls `apply_users(conn)` after the other two migrations; seeds three demo users via `INSERT OR IGNORE` (`admin/adminpass`, `caseworker1/caseworkerpass`, `foi_officer/foipass`); the CLI print now mentions how many users were seeded plus the demo credentials so a first-time dev sees them.
  - `requirements.txt` — added `flask-login`.
  - `tests/conftest.py` — restructured: **`anon_client`** does all setup + creates a `testuser` account but does **not** log in; **`client`** composes over `anon_client` by POSTing `/login`. Existing tests using `client` continue to pass unchanged. `TEST_USERNAME` / `TEST_PASSWORD` exported for `test_auth.py`.
  - `tests/test_security.py` — inline fixture updated: applies `apply_users`, seeds a `testuser`, logs in before yielding. (`test_security.py` still has its own fixture — kept in place per "don't delete another agent's setup" convention; behaviour parity with conftest.)
  - `tests/test_audit_write.py` — fixture parallels the above; `_audit_rows()` **now filters `entity_type='request'`** so the fixture's login row doesn't inflate the per-test counts; **`actor` assertions flipped from `'unknown'` to `'testuser'`** (AUD-3 evidence).
  - `tests/test_retention_schema.py` — same fixture update.
  - `tests/test_logging.py::test_log_format_produces_expected_shape` — new format string with the `user` field asserted.

- **Why:**
  - `plan.md` §7 open question #1 (HASEEB's users-table schema) — resolved by implementing it ourselves rather than waiting.
  - `plan.md` §AUD-3 (audit actor flip) — was gated on login; now done.
  - `plan.md` §OPS-5 has been extended to include `user` in the log format — an ICO auditor tracing an incident by log entries alone can now see *who*, not just *what*.
  - Gap-analysis PR #8 flagged auth as item #1 (BLOCKING). This closes that gap.

- **Design choices worth noting:**
  - **`current_actor()` centralised**, not sprinkled. If AUD-3 ever needs to change again (e.g. for service accounts, API tokens) the change is a single function.
  - **Login/logout are their own audit actions** (`entity_type='user'`) — kept separate from request-scoped rows so the auditor can filter `SELECT * FROM audit_log WHERE action IN ('login','login_failed','logout')` for the security event trail cleanly.
  - **`login_failed` never contains the password** — only the attempted username, truncated to 80 chars to guard against giant-payload log spam.
  - **Same failure message** for wrong-password vs unknown-user (tested). Standard practice — don't help an enumerator confirm which usernames exist.
  - **`_safe_next()` refuses off-site redirects** (`//evil.example.com`, `https://…`). Tested.
  - **`SESSION_COOKIE_SAMESITE='Lax'`** as the CSRF-lite defence for now. Full CSRF tokens (Flask-WTF) would be the next hardening pass — documented as a follow-up rather than shipped now.
  - **Passwords hashed with `werkzeug.security.generate_password_hash`** — no extra dep, uses `scrypt` by default in current werkzeug. Migrating to argon2 later means one call site (`hash_password()`) plus a rehash-on-login pass.
  - **`/api/healthz` intentionally auth-free** — external monitors and container HEALTHCHECK must work without credentials.

- **Verification:**
  - Unit: `python -m pytest` → **100/100 green** (80 previous, adjusted + 20 new in `test_auth.py`).
  - Live smoke pending — will do after commit + push, in the SPA browser.

- **Trajectory notes:**
  - Two rework loops. First: after adding `@login_required` and updating conftest, `test_security.py`'s tests failed — I hadn't realised the file had its own inline fixture (a merge-conflict resolution in a previous session that put it back). Added the same treatment to that fixture. Second: audit-write tests started reporting wrong row counts because the fixture's login POST adds a `login` audit row on top. Filtered `_audit_rows()` by `entity_type='request'`.
  - Left **for the next slice**:
    - CSRF tokens (Flask-WTF) on the login/logout forms.
    - Rate-limiting login attempts (Flask-Limiter, IP-scoped).
    - Password rotation / password-change route.
    - Admin-only viewing of `/api/audit` (only role check that's still missing; currently any authed user gets it).
