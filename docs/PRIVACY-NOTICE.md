# Privacy notice — FOI Deadline Tracker

*Draft — for review by the departmental DPO before publication. Once approved, link from the app footer and the FOI submission form.*

## Who we are

The Department for Transport ("DfT", "we") is the data controller for personal data processed by the FOI Deadline Tracker. Contact for privacy matters: **[FOI inbox / DPO email — to be confirmed]**.

## Why we hold information about you

When you make a Freedom of Information (FOI) request to the department, the FOI Deadline Tracker records the request so we can:

- Meet our statutory duty under the Freedom of Information Act 2000 (respond within 20 working days).
- Correspond with you about the request.
- Report the department's FOI performance annually.

## What information we hold

| What | Why we need it |
|---|---|
| Your name | To identify who to reply to and to run our register of FOI activity |
| Contact details you provided (email, address) | To send our response |
| The subject and text of your request | To answer it and record what was asked |
| Internal case notes | So caseworkers can track the response |
| Dates (received, deadline, responded) | Statutory compliance |

## Lawful basis

Public task (UK GDPR Article 6(1)(e)) — the FOI Act 2000 gives us a statutory function that requires this processing.

## How long we keep it

See `RETENTION-POLICY.md`. In short:

- **Your personal data** (name, contact, PII in the request text): typically **3 years** after we respond.
- **The record of the request itself** (reference number, subject, dates, status): typically **6 years** — the same as our wider public-record retention.
- **Audit records** (who inside DfT accessed or changed the record): **6 years**.

Policy figures are subject to departmental sign-off — treat as guidance.

## Who sees your data inside DfT

- Caseworkers on the DfT Central FOI team, and (from 2026) two directorate FOI teams.
- The departmental FOI officer for annual reporting.
- Named individuals in the department who help draft the substantive response.

Every read and every change of your record is captured in an audit log. If an internal reviewer or the ICO asks, we can show you or them exactly who has accessed your record and when.

## Who we do not share it with

We do not sell your data. We do not share it outside DfT except:

- Where the FOI response itself is publishable (that is the point of FOI, but the requester's identity is not published).
- Where required by law (e.g. court order).

## Your rights

Under UK GDPR you have the right to:

- **Access** the personal data we hold about you (subject access request / DSAR).
- **Correct** inaccurate personal data.
- **Erasure** ("right to be forgotten") of your personal data — see below.
- **Object** to our processing.
- **Complain** to the Information Commissioner's Office (ICO): [ico.org.uk](https://ico.org.uk/).

**How to exercise these rights:** email the FOI inbox above with "Data protection request" in the subject line. We aim to reply within one calendar month.

## Right to erasure — what to expect

If you ask us to erase your data:

1. We will remove your **name** and any personal identifiers in the request text and case notes.
2. We will keep the **anonymised record** of the request (reference number, dates, subject, response) because the FOI response itself is a matter of public record.
3. We will log this action in our internal audit trail. The audit row records that erasure happened; it does not re-expose your data.

## How we secure your data

- The system is only reachable inside the departmental network — it is not on the public internet.
- Users authenticate with departmental credentials before accessing records *(planned — currently the app has no login; internal access is via a shared office machine).*
- All database writes and reads of a specific record are logged with a timestamp and (once login lands) the caseworker's username.
- The database is backed up daily. Backups are encrypted at rest on the host disk. Old backups are cycled and eventually purged.

## Changes to this notice

We may update this notice. The date at the top will change and material updates will be flagged in the app.
