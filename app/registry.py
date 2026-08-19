import sqlite3
from contextlib import contextmanager
from typing import Optional

from app import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'GET',
    status TEXT NOT NULL DEFAULT 'pending'
);
"""

DEFAULT_ENDPOINTS = [
    {"name": "Loadbalancer", "url": "http://saarthi-env-3.eba-unmxae3i.ap-south-1.elasticbeanstalk.com/api/tasks/health"},
    {"name": "Saarathi Healthcare", "url": "http://saarthi-env-3.eba-unmxae3i.ap-south-1.elasticbeanstalk.com/api/health/check"},
    {"name": "Care360", "url": "http://care360-test-env.eba-uuw3ysvy.ap-south-1.elasticbeanstalk.com/api/health/check"},
    # Self-hosted, controllable demo targets — see /dummy/health and /dummy/drift in main.py.
    # Assumes the default port (8000); if you run on a different port, use the "Register
    # demo endpoint" / "Register drift demo" buttons instead, which use the page's own origin.
    {"name": "Demo (self)", "url": "http://127.0.0.1:8000/dummy/health"},
    {"name": "Drift Demo (self)", "url": "http://127.0.0.1:8000/dummy/drift"},
]


@contextmanager
def _connect():
    conn = sqlite3.connect(config.REGISTRY_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
    finally:
        conn.close()


def seed_defaults() -> None:
    """Register the standard pilot endpoints (as pending) if the registry is empty."""
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[0]
    if count:
        return
    for entry in DEFAULT_ENDPOINTS:
        register(entry["name"], entry["url"], entry.get("method", "GET"))


def register(name: str, url: str, method: str = "GET") -> dict:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO endpoints (name, url, method, status) VALUES (?, ?, ?, 'pending')",
            (name, url, method),
        )
        conn.commit()
        return get(cur.lastrowid)


def list_all() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM endpoints ORDER BY id").fetchall()
        return [dict(row) for row in rows]


def get(endpoint_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM endpoints WHERE id = ?", (endpoint_id,)).fetchone()
        return dict(row) if row else None


def set_status(endpoint_id: int, status: str) -> Optional[dict]:
    with _connect() as conn:
        cur = conn.execute("UPDATE endpoints SET status = ? WHERE id = ?", (status, endpoint_id))
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get(endpoint_id)


def approved() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM endpoints WHERE status = 'approved'").fetchall()
        return [dict(row) for row in rows]
