# Restore drill — FOI Deadline Tracker

The point of this document isn't to describe backup scripts. It's to answer
the question the ICO auditor will ask: **"Gary's machine dies on a
Wednesday. Walk me through recovery."**

A backup that has never been restored is not a backup. This runbook is
walked through and timed, and the timing is recorded below.

## 1. What we back up and how

- **Source DB:** `$FOI_DB` (default `<repo>/data/foi.db`).
- **Backup dir:** `$BACKUP_DIR` (default `<repo>/backups/`).
- **Method:** SQLite's online backup API via `sqlite3 .backup`. Safe on a live DB.
- **File format:** `foi-YYYYMMDD-HHMMSSZ.db.gz` (UTC).
- **Schedule:** daily via cron / systemd timer at 02:00 (host-local time is fine — the *filename* uses UTC).
- **Retention:** the 14 most recent backup files are kept; older files are pruned automatically after each run. Weekly retention (8-week keep) is a **manual promotion** step (see §5) and not automatic — flagged for a future improvement.
- **Audit:** every backup writes an `action='backup'` row to `audit_log` in the live DB. Every restore writes an `action='restore'` row to the newly-restored DB.

## 2. Manual backup (rehearsal)

```bash
./scripts/backup.sh
```

Expected output:
```
Backup complete: /path/to/backups/foi-20260715-132428Z.db.gz
```

Verify:
```bash
ls -lh backups/
sqlite3 data/foi.db "SELECT * FROM audit_log ORDER BY id DESC LIMIT 1;"
# Expect: newest row shows action='backup', actor='system', reason=<the backup path>
```

## 3. The drill — "Gary's machine dies"

**Setup — pretend disaster:**

```bash
# 1. Make sure there's a recent backup to restore from.
./scripts/backup.sh
ls -lh backups/     # should have at least one .db.gz

# 2. Note what's in the DB right now, so we can compare after restore.
sqlite3 data/foi.db "SELECT COUNT(*) FROM requests;"     # e.g. 13
sqlite3 data/foi.db "SELECT MAX(id) FROM requests;"      # e.g. 13
sqlite3 data/foi.db "SELECT COUNT(*) FROM audit_log;"    # some number

# 3. Simulate the disaster — remove the live DB.
rm data/foi.db
```

**Recovery:**

```bash
# 4. Restore from the most recent backup.
./scripts/restore.sh $(ls -t backups/foi-*.db.gz | head -1)
```

Expected output:
```
smoke test ok: 13 rows in requests
restored backups/foi-20260715-132428Z.db.gz -> /path/to/data/foi.db
```

**Verify:**

```bash
# 5. The DB is back and has the pre-disaster data.
sqlite3 data/foi.db "SELECT COUNT(*) FROM requests;"   # matches step 2 (e.g. 13)
sqlite3 data/foi.db "SELECT * FROM audit_log ORDER BY id DESC LIMIT 2;"
# Expect: newest row is the restore itself, action='restore'.
```

## 4. Known limitation — the "backup"-of-the-backup

The `action='backup'` audit row is written **after** the SQLite snapshot is
taken. That means the audit trail of "we ran the 02:00 backup on Tuesday"
lives in the **current** live DB, not inside any backup file.

If the DB is destroyed, the restored DB will not contain the audit rows for
backups taken *after* the one you restored from. The backup files themselves
(and their `mtime`s on the filesystem) are the durable evidence of "we did a
backup at time T"; the audit_log is the DB-side evidence.

This is a fundamental ordering problem (you can't include "I backed up at
T" inside a snapshot taken at T). A future improvement would be to keep a
separate append-only backup log outside the DB. Not doing this today.

## 5. Weekly retention (manual promotion)

Automated retention keeps the last 14 daily backups. To keep older weekly
snapshots for the ICO audit trail:

```bash
# On the first day of each week, copy the newest daily to a weekly slot.
cp "$(ls -t backups/foi-*.db.gz | head -1)" backups/weekly/foi-$(date -u +%Y-W%V).db.gz
# Prune weeklies older than 8 weeks manually.
```

Track this in `docs/AI_LOG.md` when it's done (proof-of-life for the ICO).

## 6. Drill log

Record every time this drill is walked through end-to-end. An auditor will
ask *"when did you last test recovery?"* — this table is the answer.

| Date       | Operator     | Restored from            | Notes                       | Time (min) |
|------------|--------------|--------------------------|-----------------------------|------------|
| YYYY-MM-DD | \<name\>     | foi-YYYYMMDD-HHMMSSZ.db.gz | first drill / any surprises | X          |

*(This table is intentionally started empty — fill in the first row after
the first real drill.)*
