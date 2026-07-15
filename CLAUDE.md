# Claude context — FOI Deadline Tracker

The context an agent (or human) needs before touching this repo. Two parts:

1. **Repository conventions** — identity, git workflow, commit format, logging.
2. **Project shape** — what this Flask app is and how it's wired.

---

## Part 1 — Repository conventions

### Agent identity

Before doing anything else in this repo, ask the user for an identifying name (e.g. `Agent1`, `Agent-Jack`). Use this identifier in:

- Every commit message (prefix with `[AgentName]`)
- Every `Agent_log.md` entry
- Any notes or instructions left for other agents in plans or documents

### Git workflow

This repo is shared — multiple agents commit and push simultaneously. Follow this sequence for every task, without exception.

#### 1. Before making any file changes

- Run `git pull --rebase`
- If there are conflicts, resolve them preserving both agents' intent — never discard another agent's work
- If a conflict is large or ambiguous, discuss with the user before resolving

#### 2. Do the work

#### 3. Before committing

- Add an `Agent_log.md` entry if the task requires one (see §"Two records, two jobs" below)

#### 4. Commit

- Stage only the relevant files — never `git add .` without checking `git status` first
- Every commit message must:
  - Start with `[AgentName]` followed by a short summary (first line under 72 chars)
  - Include a body explaining what changed and why (one bullet per file or concern is fine)

#### 5. Push

- Run `git pull --rebase` once more before pushing, in case another agent pushed while you were working
- Push immediately — do not leave commits sitting unpushed

### Commit message example

```
[AgentName] Add eligibility logic and unit tests

- src/utils/eligibility.js: pure function implementing 5 priority-ordered
  rules from the content plan; returns { result, measures }
- src/utils/eligibility.test.js: 7 tests covering all ineligible paths,
  eligible path, partial-renter path, and measures logic
```

### Two records, two jobs: commit messages vs Agent_log

This repo keeps two written records. They are complementary, not duplicates — never copy rationale from one into the other.

**Commit messages are the collaboration audit log.** They capture the final-state rationale: why the committed code or docs look the way they do. Git is the right home for this because it is distributed, attributed, timestamped, immutable once pushed, and conflict-free on history — exactly what parallel agents on different machines need to reconstruct who changed what, why, and in what order. Use `git log`, `git blame`, and `git log -- <path>`.

**`Agent_log.md` is the AI-assistance trajectory.** It captures what git cannot: the path to the final state — what the AI first generated, what was wrong or incomplete about it, and what the human changed and why. The AI's rejected first draft never becomes a commit, so this provenance lives nowhere else. It covers both code and doc/process changes, and is required by the project rubric.

**Rule of thumb:** if a task was a one-shot success, the commit message says everything and no `Agent_log.md` entry is needed. If it took meaningful iteration (substantive correction or change of direction — not a typo fix), log the trajectory in `Agent_log.md`.

### Instruction file refinement

Where a recurring pattern or preference is encountered, suggest adding or updating one or more agent instruction files (this file and any nested equivalents) to most efficiently achieve the desired behaviour going forwards.

### Web research

When performing web research, save the content of important sources to a local document store with clear research provenance (source URL and date retrieved). This store can be referenced and updated as necessary going forward.

---

## Part 2 — Project shape

Small Flask app the DfT central FOI team uses to log requests and compute the statutory 20-working-day deadline. This will be audited by the ICO in autumn.

**Shape:** single-page app. `/` returns one HTML shell; the browser talks to `/api/requests[/{id}]` via `fetch()`. This is required because the lab environment serves the app under a proxy prefix (`/proxy/5002/`), and server-rendered navigation to `/request/<id>` breaks under that prefix.

### Project structure

```
foi_tracker/    Application package — Flask app, routes, deadline logic, audit helper, templates
tests/          Pytest suite (run with `python -m pytest`)
scripts/        seed.py, migrate_*.py — run with `python -m scripts.<name>`
data/           SQLite DB lives here (ignored by git except .gitkeep)
docs/           AI_LOG.md (historical), TEAM-PLAN.txt, hackathon brief
run.py          Entry point
```

### Non-negotiable conventions

- **`SECRET_KEY` must come from the environment.** Never hard-code it, never default it. The app raises at startup if it's missing.
- **All SQL uses parameterised queries.** Never build a query with f-strings or `%` formatting. See `foi_tracker/CLAUDE.md` for the pattern.
- **`debug=True` is not committed.** Debug is opt-in via `FLASK_DEBUG=1`.
- **Fetch URLs in the frontend are relative** (`api/requests`, not `/api/…`). A `<base href="./">` in the shell locks the base to the current path so the app works under any URL prefix (e.g. the lab proxy).
- **Templates live in `foi_tracker/templates/`** so Flask finds them via the package. There is only one template — `app.html` — the SPA shell.
- **All user-controlled data going into the DOM must go through `esc()`.** See `foi_tracker/CLAUDE.md`.
- **`audit_log` is append-only.** Enforced by SQLite triggers; do not add routes that UPDATE or DELETE from it.

### What has already been done

- SQL injection closed — parameterised queries in every path.
- `SECRET_KEY` required from env; `debug=True` removed; `FOI_DB` env var overrides the DB path.
- Repo restructured into `foi_tracker/` / `tests/` / `scripts/` / `docs/`.
- Single-page app + JSON API (`/api/requests[/{id}]`).
- Pytest infrastructure — see `tests/CLAUDE.md`.
- Default DB path moved off the code directory (`data/foi.db`); `scripts/seed.py` refuses to overwrite without `--force`.
- `audit_log` table + immutability triggers via `scripts/migrate_add_audit_log.py`.
- Audit write path (`foi_tracker/audit.py`) instrumenting create / view / update endpoints. Actor is currently `'unknown'` — flipped to `current_user.username` when login lands.

### Workflow (project-specific)

- Every change goes on a branch (`fix/…`, `feature/…`, `security/…`, `operations_GDPR_audit`, etc.).
- Tests must pass (`python -m pytest`) before pushing.
- Add an entry to `Agent_log.md` for any non-trivial change.
- Team ownership: see `docs/TEAM-PLAN.txt`.

### Currently in flight

- Bank-holiday-aware deadline calculation (Serena) — `foi_tracker/deadlines.py`
- Basic auth / login (Haseeb) — dependency for AUD-3 (audit-log actor flip)
- Operations, GDPR, audit log continuation (Satyavrat, on `operations_GDPR_audit` branch)
