# Data Protection Impact Assessment — FOI Deadline Tracker

**System:** FOI Deadline Tracker (small Flask app + SQLite).
**Owner:** DfT Central FOI team.
**Version:** Draft 1 — 2026-07-16.
**Status:** *awaiting departmental DPO review*.

*ICO guidance recommends a DPIA when processing is likely to result in high risk to individuals. Two changes here trigger a fresh DPIA: (1) two additional directorates gaining access, expanding who can see requester data; (2) an upcoming ICO audit which will examine handling of personal data.*

## 1. Nature, scope, context, purpose

**Nature:** a small internal web app the FOI team uses to log requests and track the statutory 20-working-day deadline. SQLite database, no external services beyond the public GOV.UK bank holidays API.

**Scope:** currently ~6 users (Central FOI team). Two additional directorate teams (~ another 10–15 users) are being onboarded. Data subject count grows with request volume — order of 100–300 new requesters per year across the department.

**Context:** the previous system was a shared spreadsheet on a network drive with no per-user access control and no audit trail. Backups were manual and untested. This replacement is the response to the upcoming ICO audit.

**Purpose:** statutory FOI compliance under FOI Act 2000. Personal data is processed only to correspond with requesters and to record who asked what, when.

## 2. Necessity and proportionality

- **Legal basis:** public task — UK GDPR Article 6(1)(e).
- **Minimisation:** the schema does not include DOB, national identifier, or any special category data. `notes` is free-text and represents the largest minimisation risk (see §4 R3).
- **Storage limitation:** retention policy at `RETENTION-POLICY.md` — 3 years for PII, 6 years for the anonymised record and audit log.
- **Alternatives considered:** an off-the-shelf case-management system (rejected — cost, procurement time, over-scoped). A shared spreadsheet (rejected — this is what we're replacing).

## 3. Data flow

```
[Requester]
    │
    │  (email, letter, WhatDoTheyKnow, etc. — external to this system)
    ▼
[FOI inbox / caseworker]
    │
    │  Manually types the request into the app
    ▼
[Flask app /api/requests]
    │
    ├─▶ [SQLite:  requests]           name + PII in notes
    └─▶ [SQLite:  audit_log]          who/when/action, before/after JSON
    │
    │  Every mutation is atomic with its audit row.
    ▼
[Caseworker views/updates in the SPA]
    │  Views + updates append audit_log rows. List reads are not logged.
    ▼
[Nightly backup via sqlite3 .backup + gzip]  ──▶  local backups/ dir
```

No data leaves the host except for backup files copied to the departmental backup server (out of scope of the app, in scope of the ops team's own DPIA).

## 4. Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation | Residual |
|---|---|---|---|---|---|
| R1 | Unauthorised internal access — a colleague opens a record they shouldn't | Medium (until login lands) | Medium | Audit log captures every access. Login + team-scoped filtering (DP-4) will land with Haseeb's auth work. | Medium until AUD-3 / DP-4 |
| R2 | SQL injection through the search box | Was **high** | High | Closed — all four query sites parameterised. Regression tests in `tests/test_security.py`. | Very low |
| R3 | Caseworker pastes further PII (address, correspondence) into free-text `notes` — increasing the data-minimisation footprint | High | Medium | Training. UI hint (planned). `notes` covered by the same retention + erasure as `requester`. | Medium — behavioural |
| R4 | Backup theft / loss (USB stick / laptop) | Was **high** | High | Backups now automated to a controlled dir, off the code path, with tested restore. Host disk is expected to be full-disk encrypted; backup files should be gpg/age-encrypted before leaving the host (DP-6, planned). | Medium until DP-6 |
| R5 | Audit-log tampering (someone with SQL access edits history) | Low | High | `BEFORE UPDATE` / `BEFORE DELETE` triggers on `audit_log` reject any modification. Tested. Optional future work: hash chain (AUD-4). | Low |
| R6 | DB corruption / disk failure — total data loss | Medium | High | Nightly automated backup (OPS-3). Tested restore drill in `docs/RESTORE-DRILL.md`. | Low |
| R7 | Runs on Gary's desktop — single point of failure | Was **high** | Medium | Deployment moved to a managed host under systemd or Docker (OPS-4). Restart-on-failure. `HEALTHCHECK` on `/api/healthz` for external monitoring. | Low |
| R8 | Session-token forgery from a weak `SECRET_KEY` | Was **high** | High | Closed — app refuses to start without `SECRET_KEY` in env. `install.sh` generates a 64-hex-char secret at first install. | Very low |
| R9 | Cross-team leakage after directorates onboard | Medium | Medium | `team_id` column already in the schema (DP-1, done). Query-time scoping and role-based override (DP-4) lands with login. | Medium until DP-4 |
| R10 | Right-to-erasure request received — no route to fulfil cleanly | Currently **medium** | Medium | Manual process documented in `RETENTION-POLICY.md` §5 until DP-2 endpoint lands. Every manual erasure written to `audit_log`. | Medium until DP-2 |

## 5. Consultation

- **Data subjects (requesters):** privacy notice at `docs/PRIVACY-NOTICE.md` to be published on the FOI submission page.
- **Internal users (caseworkers):** current team involved directly (Central FOI). Onboarding of two directorate teams triggers a further review.
- **DPO:** *pending sign-off*.
- **ICO:** not directly consulted; guidance followed via ICO time-limits and access rights pages.

## 6. Sign-off

- [ ] System owner (Central FOI team lead): *pending*
- [ ] Data Protection Officer: *pending*
- [ ] Chief Information Security Officer: *pending*

## 7. Review cadence

- Annually.
- On any material change to data collected, users, or hosting.
- After any personal-data incident.
