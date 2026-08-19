from contextlib import contextmanager

import psycopg2

from app import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS endpoints (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'GET',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS access_log (
    id SERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    action TEXT NOT NULL,
    status_code INTEGER,
    latency_ms REAL,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE access_log ADD COLUMN IF NOT EXISTS detail TEXT;
"""


@contextmanager
def get_connection():
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(config.REQUEST_TIMEOUT_SECONDS * 1000)}")
        yield conn
    finally:
        conn.close()


def init_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)


def log_access(
    actor: str,
    endpoint: str,
    action: str,
    status_code: int | None = None,
    latency_ms: float | None = None,
    detail: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO access_log (actor, endpoint, action, status_code, latency_ms, detail)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (actor, endpoint, action, status_code, latency_ms, detail),
            )


def list_access_log(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, actor, endpoint, action, status_code, latency_ms, detail, created_at
                FROM access_log
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
