import sqlite3
import statistics
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from app import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS latency_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    status_code INTEGER,
    ok INTEGER NOT NULL,
    attempts INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_latency_history_endpoint ON latency_history (endpoint, id);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(config.HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        try:
            conn.execute("ALTER TABLE latency_history ADD COLUMN attempts INTEGER")
        except sqlite3.OperationalError:
            pass  # column already exists (pre-existing db file)
        yield conn
    finally:
        conn.close()


def record(endpoint: str, latency_ms: float, status_code: Optional[int], ok: bool, attempts: int, timestamp: datetime) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO latency_history (endpoint, latency_ms, status_code, ok, attempts, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (endpoint, latency_ms, status_code, int(ok), attempts, timestamp.isoformat()),
        )
        conn.commit()


def overall_stats(endpoint: str, min_samples: int = 5) -> Optional[tuple[float, float]]:
    """Mean and sample standard deviation across ALL recorded successful checks for this endpoint.

    Deliberately holistic rather than a sliding recent-window average — the baseline should
    characterize the endpoint's overall behavior and stay stable check-to-check, not drift with
    whatever the last N samples happened to be.

    Returns None if there aren't enough samples yet to characterize the baseline.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT latency_ms FROM latency_history WHERE endpoint = ? AND ok = 1",
            (endpoint,),
        ).fetchall()
    if len(rows) < min_samples:
        return None
    values = [r["latency_ms"] for r in rows]
    return statistics.mean(values), statistics.stdev(values)


def recent_values(endpoint: str, limit: int) -> list[float]:
    """Latencies of the last `limit` successful checks, oldest first — for trend/slope analysis."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT latency_ms FROM (
                SELECT latency_ms FROM latency_history
                WHERE endpoint = ? AND ok = 1
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (endpoint, limit),
        ).fetchall()
    return [r["latency_ms"] for r in reversed(rows)]


def recent_checks(limit: int = 200) -> list[dict]:
    """The last `limit` checks across all endpoints, most recent first — for hydrating the UI on load."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM latency_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
