"""
One-time auth schema setup -- mirrors db/init_db.py's pattern exactly, but
applies auth_schema.sql instead of schema.sql, so init_db.py itself is
never touched. Safe to re-run.

Usage: python3 -m db.init_auth_db
(Run db/init_db.py first, or run this any time after -- it only depends on
pgcrypto, which init_db.py already enables; if this is run standalone it
enables pgcrypto itself too, so order doesn't actually matter.)
"""

from pathlib import Path

from db.connection import get_connection

AUTH_SCHEMA_PATH = Path(__file__).resolve().parent / "auth_schema.sql"


def init_auth_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # gen_random_uuid()
        cur.execute(AUTH_SCHEMA_PATH.read_text())
        conn.commit()
        cur.close()
    print("Auth schema applied.")


if __name__ == "__main__":
    init_auth_db()
