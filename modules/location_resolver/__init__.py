"""
[0] LOCATION RESOLVER

Input:  village / block / district / city / state text (typed or, later,
        spoken) — anywhere in India, not just the curated dataset.
Output: canonical location record — LGD code, block, district, region,
        coordinates.

Matching strategy, in order:
  1. Curated dataset: exact match, then location_id/lgd_code, then trigram
     fuzzy match (pg_trgm) — the 200-location Tamil Nadu dataset loaded by
     db/ingest_raw_data.py. Real district names, synthetic sub-district
     detail (see docs/DATA_DECISIONS.md).
  2. Gazetteer + auto-synthesis fallback (modules/location_resolver/synth.py):
     any locality/city/state anywhere in India that isn't in the curated
     dataset resolves via the offline gazetteer, and a full synthetic data
     footprint (population, competitors, market prices) is generated for it
     on demand — deterministically and idempotently — so the pipeline never
     errors out on an unrecognized place. Every such row is tagged
     'auto_generated_synthetic_no_ground_truth' so this is never mistaken
     for real Census/EC data.

No external geocoding call in the request path (R1) — everything here is a
local DB lookup or local deterministic generation.
"""

from db.connection import get_cursor
from modules.location_resolver.synth import LocationNotRecognized, ensure_location_exists


class LocationNotFound(Exception):
    pass


class LocationAmbiguous(Exception):
    """Raised when free-text input matches more than one location and the
    caller must disambiguate (e.g. present a short list to the user)."""

    def __init__(self, candidates: list[dict]):
        self.candidates = candidates
        super().__init__(f"{len(candidates)} candidate locations matched")


def resolve_location(place_query: str, district_hint: str | None = None) -> dict:
    """Resolve free-text location input to a canonical location record.

    Returns a dict with location_id, lgd_code, village, block, district,
    region, state, latitude, longitude, urban_rural_flag.
    """
    query = place_query.strip()
    if not query:
        raise LocationNotFound("Empty location query")

    with get_cursor() as cur:
        # 1. Exact (case-insensitive) match on village name, optionally
        #    narrowed by district when the caller already knows it.
        if district_hint:
            cur.execute(
                """
                SELECT * FROM villages
                WHERE lower(village) = lower(%s) AND lower(district) = lower(%s)
                """,
                (query, district_hint),
            )
        else:
            cur.execute("SELECT * FROM villages WHERE lower(village) = lower(%s)", (query,))
        rows = cur.fetchall()
        if len(rows) == 1:
            return dict(rows[0])
        if len(rows) > 1:
            raise LocationAmbiguous([dict(r) for r in rows])

        # 2. Exact match on location_id or lgd_code (structured input).
        cur.execute(
            "SELECT * FROM villages WHERE location_id = %s OR lgd_code = %s",
            (query, query),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

        # 3. Fuzzy fallback — trigram similarity on village name.
        cur.execute(
            """
            SELECT *, similarity(village, %s) AS match_score
            FROM villages
            WHERE village %% %s
            ORDER BY match_score DESC
            LIMIT 5
            """,
            (query, query),
        )
        candidates = [dict(r) for r in cur.fetchall()]

    if candidates and (len(candidates) == 1 or candidates[0]["match_score"] >= 0.6):
        return candidates[0]
    if len(candidates) > 1:
        raise LocationAmbiguous(candidates)

    # 4. Not in the curated dataset at all — gazetteer + auto-synthesis.
    # This is what makes "Koramangala", "Bengaluru", or any other Indian
    # state/district resolve without error (see synth.py's docstring).
    return ensure_location_exists(query)


def get_population(location_id: str) -> dict:
    """Population/catchment-default figures for a resolved location."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM population WHERE location_id = %s", (location_id,))
        row = cur.fetchone()
    if not row:
        raise LocationNotFound(f"No population record for location_id '{location_id}'")
    return dict(row)
