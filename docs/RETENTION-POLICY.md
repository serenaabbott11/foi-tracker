# Retention policy — FOI Deadline Tracker

**Owner:** DfT Central FOI team.
**Reviewed:** 2026-07-16. **Next review:** 2027-07-16.
**Status:** *hackathon draft — retention periods below need to be confirmed with the departmental Records Officer and DPO before this is treated as policy.*

## 1. What personal data we hold

The application stores per-request:

| Field | Category | Source |
|---|---|---|
| `requester` | Personal data — name (sometimes with organisation) | Requester's submission |
| `subject` | Free-text; may contain personal data indirectly | Requester's submission |
| `notes` | Free-text; **high risk** of caseworkers pasting further personal data (addresses, correspondence) | Internal |
| `ref`, `received`, `deadline`, `status`, `created_at`, `updated_at`, `responded_at`, `retention_until`, `team_id` | Operational metadata | System |

The `audit_log` table additionally records `actor` (username, currently `'unknown'` until AUD-3), `actor_ip`, `action`, `before_json`, `after_json` for every audit-relevant event.

## 2. Lawful basis

**Public task** (UK GDPR Article 6(1)(e)) — the FOI Act 2000 requires the department to log, track, and respond to information requests. Special category data is not intentionally collected; caseworkers must not enter it into `notes`.

## 3. Retention schedule

| Data | Kept for | Trigger | Owner |
|---|---|---|---|
| `requests` row (operational metadata: `ref`, `received`, `deadline`, `status`, `responded_at`) | **6 years** from `responded_at` | Public record of the FOI response; matches Public Records Act practice | System |
| `requests` row **PII** (`requester`, `notes`) | **3 years** from `responded_at` | Balance between operational usefulness and data minimisation | DP-3 sweeper (planned) |
| `audit_log` full row | **6 years** from `timestamp` | Matches typical UK gov audit retention | DP-3 (future extension) |
| `audit_log` `before_json`/`after_json` payload | **6 years** from `timestamp` | Content of the diff is redacted after 6 years; row is retained (who/when/action/entity_id) for statistical purposes | DP-3 (future extension) |
| Backup files (`backups/foi-*.db.gz`) | Last 14 daily kept automatically; weekly promotions kept 8 weeks (manual) | See `docs/RESTORE-DRILL.md` §5 | `scripts/backup.sh` (auto) + human (weeklies) |
| `data/foi.db.pre-restore-*` safety copies | 30 days | Manual cleanup | Operator |

**Numbers above are the proposed policy, not current behaviour.** Today only backup retention is fully automated (last 14 kept). Requests PII scrubbing (DP-3 sweeper) and audit_log ageing are not yet implemented; both are on `plan.md` and require the `retention_until` column populated (already provisioned in DP-1).

## 4. How the mechanism works (once complete)

1. When a request transitions to `Responded`, `responded_at` is set (DP-1, done).
2. A scheduled `scripts/retention_sweep.py` (DP-3, planned) computes `retention_until = responded_at + 3 years` and stores it.
3. When `today() > retention_until`, the sweeper nulls `requester` and scrubs `notes`, writing an `action='erase_pii'` audit row with `actor='system'`.
4. The `requests` row itself is retained until `responded_at + 6 years`, then the row is deleted with a final `action='delete'` audit row.
5. The `audit_log` row for those actions itself falls under the 6-year audit retention.

## 5. Right to erasure requests

A requester emailing the FOI inbox with an Article 17 request is currently handled manually (there is no `POST /api/requests/<id>/erase-pii` endpoint yet — DP-2, blocked on login). Until that endpoint exists, the operator:

1. Opens the request in the SPA, empties `notes`, saves.
2. Runs `sqlite3 data/foi.db "UPDATE requests SET requester = NULL WHERE id = ?"`.
3. Manually inserts an `audit_log` row with `action='erase_pii'`, `reason=<email quote>`, `actor='system'`.

This is documented, not endorsed — the sooner DP-2 lands the sooner this becomes a one-command operation with proper auditing.

## 6. Deletion of backup files

Backup files are subject to the same policy — if a requester's data is erased from the live DB, backups containing that data are still on disk until they age out (14 days for daily backups; up to 8 weeks for weekly promotions). This is the standard "reasonable steps" position under UK GDPR — full deletion from all backup media is not required, provided:

- The data is not restored to a live system.
- Backups are cycled on the documented retention.
- Restores are audit-logged (already implemented — see `docs/RESTORE-DRILL.md`).

## 7. Review cadence

Reviewed annually or whenever:

- The `requests` schema changes.
- A new team joins (retention may differ per directorate).
- ICO guidance changes.
- An incident (data breach, DSAR complaint) exposes a gap.

## 8. Open questions for the FOI officer

- Is the 3-year PII / 6-year record retention correct for DfT, or does the department have its own policy?
- Are there statutory exceptions (public inquiry hold, legal disclosure hold) that override the sweep?
- Do the two joining directorates share this retention or set their own?
