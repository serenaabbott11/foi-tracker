"""OPS-1: seed refuses to overwrite an existing DB without --force."""
import os
import sqlite3
import tempfile

import pytest

from scripts.seed import seed


@pytest.fixture
def tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_seed_creates_new_db(tmp_db_path):
    seed(tmp_db_path)
    assert os.path.exists(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    conn.close()
    assert count > 0


def test_seed_refuses_to_overwrite_existing_db(tmp_db_path):
    # Create an empty file at the path so seed sees it as "existing".
    with open(tmp_db_path, "w"):
        pass

    with pytest.raises(SystemExit, match="already exists"):
        seed(tmp_db_path)


def test_seed_overwrites_with_force(tmp_db_path):
    with open(tmp_db_path, "w") as f:
        f.write("not a sqlite file")

    seed(tmp_db_path, force=True)

    conn = sqlite3.connect(tmp_db_path)
    count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    conn.close()
    assert count > 0


def test_seed_creates_parent_dir(tmp_path):
    # tmp_path is a pytest-provided Path; ensure seed creates the parent dir.
    nested = tmp_path / "nested" / "sub" / "foi.db"
    assert not nested.parent.exists()

    seed(str(nested))

    assert nested.exists()
    assert nested.parent.is_dir()
