# Restore drill — FOI Deadline Tracker

The point of this document isn't to describe backup scripts. It's to answer
the question the ICO auditor will ask: **"Gary's machine dies on a
Wednesday. Walk me through recovery."**

A backup that has never been restored is not a backup. This runbook is
walked through and timed, and the timing is recorded below.

## 1. What we back up and how

- **Source DB:** `$FOI_DB` (default `<repo>/data/foi.db`).
- **Backup dir:** `$FOI_BACKUP_DIR` (default `<repo>/data/backups/`).
- **Method:** SQLite's online backup API. Safe on a live DB.
- **File format:** `foi-YYYYMMDD-HHMMSS.db` (UTC).
- **Schedule:** daily via cron / systemd timer at 02:00 (host-local time is fine — the *filename* uses UTC).
- **Retention:** the newest `FOI_BACKUP_KEEP` (default 14) files are kept; older ones are pruned automatically after each run.
- **Verification:** every backup runs `PRAGMA integrity_check` before it counts.

## 2. Manual backup (rehearsal)

```bash
python -m scripts.backup
```

Expected output:
```
Backup written: data/backups/foi-20260716-020000.db
```

Verify:
```bash
ls -lh data/backups/
```

## 3. The drill — "Gary's machine dies"

**Setup — pretend disaster:**

```bash
# 1. Make sure there's a recent backup to restore from.
python -m scripts.backup
ls -lh data/backups/     # should have at least one .db file

# 2. Note what's in the DB right now, so we can compare after restore.
sqlite3 data/foi.db "SELECT COUNT(*) FROM requests;"     # e.g. 13

# 3. Simulate the disaster — remove the live DB.
rm data/foi.db
```

**Recovery:**

```bash
# 4. Restore from the most recent backup (default: newest).
python -m scripts.restore
```

Or restore from a specific file:
```bash
python -m scripts.restore data/backups/foi-20260716-020000.db
```

**Verify:**

```bash
# 5. The DB is back and has the pre-disaster data.
sqlite3 data/foi.db "SELECT COUNT(*) FROM requests;"   # matches step 2 (e.g. 13)
```

The restore also preserves the previous DB file (if any) at
`data/foi.db.pre-restore-YYYYMMDD-HHMMSS`, so you can roll back a bad restore.

## 4. Drill log

Record every time this drill is walked through end-to-end. An auditor will
ask *"when did you last test recovery?"* — this table is the answer.

| Date       | Operator     | Restored from             | Notes                       | Time (min) |
|------------|--------------|---------------------------|-----------------------------|------------|
| YYYY-MM-DD | \<name\>     | foi-YYYYMMDD-HHMMSS.db    | first drill / any surprises | X          |

*(This table is intentionally started empty — fill in the first row after
the first real drill.)*
