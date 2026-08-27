"""
One-time DB setup: extensions + schema. Safe to re-run (CREATE ... IF NOT
EXISTS throughout).

Usage: python3 -m db.init_db
"""

from pathlib import Path

from db.connection import get_connection

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")   # fuzzy village-name matching
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # gen_random_uuid()
        cur.execute(SCHEMA_PATH.read_text())
        conn.commit()
        cur.close()
    print("Schema applied.")


if __name__ == "__main__":
    init_db()
