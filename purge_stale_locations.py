"""
One-off cleanup: removes every villages row (and its dependent
population/competitors/catchment_cache rows) that was synthesized under the
OLD fake-pin fallback -- identified by the sentinel state text
"Unrecognized (auto-placed, not geocoded)". Safe to run any number of
times; it only ever touches rows carrying that exact sentinel, never a
real curated-dataset row or a legitimately gazetteer-resolved one.

Run this from your artha_setu folder, with the same Python environment
your backend uses:

    python purge_stale_locations.py

If your DB isn't at the default localhost:5432/artha_setu, set
DATABASE_URL first, same as when running the server.
"""

import os

import psycopg2

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:artha_setu_dev@localhost:5432/artha_setu")
STALE_STATE = "Unrecognized (auto-placed, not geocoded)"

conn = psycopg2.connect(DSN)
conn.autocommit = False
cur = conn.cursor()

cur.execute("SELECT location_id, village, district FROM villages WHERE state = %s", (STALE_STATE,))
rows = cur.fetchall()

if not rows:
    print("No stale fake-pin rows found. Nothing to clean up.")
else:
    print(f"Found {len(rows)} stale row(s):")
    for location_id, village, district in rows:
        print(f"  {location_id}  ({village}, {district})")

    for location_id, _, _ in rows:
        cur.execute("DELETE FROM population WHERE location_id = %s", (location_id,))
        cur.execute("DELETE FROM competitors WHERE location_id = %s", (location_id,))
        cur.execute("DELETE FROM catchment_cache WHERE location_id = %s", (location_id,))
        cur.execute("DELETE FROM villages WHERE location_id = %s", (location_id,))

    conn.commit()
    print(f"Deleted {len(rows)} stale row(s) and their dependent data.")

cur.close()
conn.close()
