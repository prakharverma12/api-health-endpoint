import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from app import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    action TEXT NOT NULL,
    status_code INTEGER,
    latency_ms REAL,
    detail TEXT,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(config.AUDIT_DB_PATH)
    try:
        conn.executescript(_SCHEMA)
        try:
            conn.execute("ALTER TABLE access_log ADD COLUMN detail TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists (pre-existing db file)
        yield conn
    finally:
        conn.close()


def log(
    actor: str,
    endpoint: str,
    action: str,
    status_code: Optional[int] = None,
    latency_ms: Optional[float] = None,
    detail: Optional[str] = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO access_log (actor, endpoint, action, status_code, latency_ms, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (actor, endpoint, action, status_code, latency_ms, detail, datetime.now().isoformat()),
        )
        conn.commit()


def list_recent(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM access_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
