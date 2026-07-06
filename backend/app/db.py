"""
Lightweight SQLite store for user settings (GreenAPI credentials etc.)
No ORM needed — simple key/value table with a settings JSON blob per user_id.
"""
import json
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "settings.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id     TEXT PRIMARY KEY,
                settings    TEXT NOT NULL DEFAULT '{}',
                updated_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


def get_settings_for_user(user_id: str = "default") -> dict:
    init_db()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT settings FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return json.loads(row["settings"])
        return {}


def save_settings_for_user(settings: dict, user_id: str = "default") -> None:
    init_db()
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO user_settings (user_id, settings, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                settings   = excluded.settings,
                updated_at = excluded.updated_at
        """, (user_id, json.dumps(settings)))
        conn.commit()
