# Filesystem paths — the single source of truth for where data lives.
#
# Importing this module has NO side effects and requires NO environment
# variables (unlike foi_tracker.app, which demands SECRET_KEY). That lets the
# backup/restore tooling reuse these paths without booting the Flask app.

import os
from pathlib import Path

# Repo root = the parent of the foi_tracker package.
ROOT = Path(__file__).resolve().parent.parent

# Data lives OUTSIDE the code tree, so editing code — or re-running seed.py —
# never sits on top of the live database. All three are overridable for tests
# and alternate deployments.
DATA_DIR = Path(os.environ.get("FOI_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("FOI_DB", DATA_DIR / "foi.db"))
BACKUP_DIR = Path(os.environ.get("FOI_BACKUP_DIR", DATA_DIR / "backups"))


def ensure_dirs():
    """Create the data and backup directories if they don't exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
