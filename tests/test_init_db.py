import os
import sqlite3
import tempfile
import types
from pathlib import Path

import pytest

import app as app_module


def test_init_db_handles_existing_schema_without_duplicate_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL)"
    )
    conn.execute("ALTER TABLE users ADD COLUMN level_german TEXT NOT NULL DEFAULT 'noob'")
    conn.commit()
    conn.close()

    monkeypatch.setattr(app_module, "DATABASE", str(db_path))
    app_module.init_db()

    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    assert "level_german" in cols
    conn.close()
