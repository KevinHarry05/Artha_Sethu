"""
PostgreSQL connection layer. Single source of truth for how every module
reaches the database — engines never open their own connections.

Connection string comes from DATABASE_URL; falls back to local dev default
so `pytest` works out of the box in a fresh dev environment.
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

DEFAULT_DSN = "postgresql://postgres:artha_setu_dev@localhost:5432/artha_setu"


def get_dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


@contextmanager
def get_connection():
    conn = psycopg2.connect(get_dsn())
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(commit: bool = False):
    """Yields a RealDictCursor (rows come back as dicts, not tuples)."""
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        finally:
            cur.close()
