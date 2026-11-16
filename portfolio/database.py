"""Tiny SQLite layer for contact messages (stdlib only, no ORM)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    email      TEXT    NOT NULL,
    message    TEXT    NOT NULL,
    ip_hash    TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages (created_at DESC);
"""


def get_db() -> sqlite3.Connection:
    """Return the per-request connection, opening it on first use."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app: Flask) -> None:
    """Create the database file and tables if they do not exist."""
    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


def save_message(name: str, email: str, message: str, ip_hash: str) -> int:
    db = get_db()
    cursor = db.execute(
        "INSERT INTO messages (name, email, message, ip_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, email, message, ip_hash,
         datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    db.commit()
    return int(cursor.lastrowid)


def list_messages(limit: int = 50) -> list[dict[str, Any]]:
    rows = get_db().execute(
        "SELECT id, name, email, message, created_at FROM messages "
        "ORDER BY id DESC LIMIT ?",
        (max(1, min(limit, 500)),),
    ).fetchall()
    return [dict(row) for row in rows]


def count_messages() -> int:
    return int(get_db().execute("SELECT COUNT(*) FROM messages").fetchone()[0])
