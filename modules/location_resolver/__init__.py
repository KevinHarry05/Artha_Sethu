"""
[0] LOCATION RESOLVER

Input:  a 6-digit PIN code.
Output: canonical location record — LGD code, block, district, region,
        coordinates.

CHANGED (deliberately, for now): this used to accept free-text village /
locality / city / state input, matched via exact text match, then trigram
fuzzy match, then an offline gazetteer + auto-synthesis fallback for
anything outside the curated dataset (see synth.py's docstring for why
that auto-synthesis fallback itself was later tightened to raise instead
of fabricating a coordinate). That entire free-text path is now bypassed:
resolve_location() takes a PIN code and matches it exactly against the
`pincode` column loaded from 01_locations.csv (see db/ingest_raw_data.py).

Why: PIN codes are unambiguous where place names aren't — no typos to
fuzzy-match, no "which Chengalpattu did you mean", no risk of a
free-text guess landing on a real place with the same name outside India.
The tradeoff is scope: only the curated 200-location Tamil Nadu dataset is
covered right now, not "any state, any locality" the way the old gazetteer
fallback advertised. modules/location_resolver/synth.py and gazetteer.py
are left in place, unused by this function, in case free-text input needs
to come back later (e.g. layered on top of an all-India PIN code
directory) -- LocationNotRecognized is reused from there since its
(query, suggestions) shape already fits.

Downstream code is unaffected: this function still returns the same dict
shape (location_id, lgd_code, pincode, village, block, district, region,
state, latitude, longitude, urban_rural_flag) it always did, so
pipeline.py, feasibility_engine, etc. don't need to change.

No external geocoding call in the request path (R1) — everything here is a
local DB lookup.
"""

from db.connection import get_cursor
from modules.location_resolver.synth import LocationNotRecognized


class LocationNotFound(Exception):
    pass


class LocationAmbiguous(Exception):
    """Raised when free-text input matches more than one location and the
    caller must disambiguate (e.g. present a short list to the user)."""

    def __init__(self, candidates: list[dict]):
        self.candidates = candidates
        super().__init__(f"{len(candidates)} candidate locations matched")


def _suggest_pincodes(limit: int = 5) -> list[str]:
    """A small sample of PIN codes this tool actually has data for, shown
    as 'did you mean' style suggestions when a code isn't found or isn't
    correctly formatted."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT pincode, village, district FROM villages ORDER BY pincode LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return [f"{r['pincode']} — {r['village']}, {r['district']}" for r in rows]


def resolve_location(pincode: str) -> dict:
    """Resolve a 6-digit PIN code to a canonical location record.

    Returns a dict with location_id, lgd_code, pincode, village, block,
    district, region, state, latitude, longitude, urban_rural_flag.
    """
    query = (pincode or "").strip()
    if not query:
        raise LocationNotFound("Empty pincode")

    is_well_formed = query.isdigit() and len(query) == 6

    with get_cursor() as cur:
        if is_well_formed:
            # 1. Exact PIN code match -- the only lookup path for
            #    user-typed input now (see module docstring).
            cur.execute("SELECT * FROM villages WHERE pincode = %s", (query,))
            row = cur.fetchone()
            if row:
                return dict(row)

        # 2. Exact match on location_id or lgd_code -- unchanged, for
        #    internal/structured callers (tests, admin tools) that already
        #    have the canonical id rather than a PIN code.
        cur.execute(
            "SELECT * FROM villages WHERE location_id = %s OR lgd_code = %s",
            (query, query),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

    suggestions = _suggest_pincodes()
    if is_well_formed:
        reason = f"PIN code '{query}' isn't in the locations this tool currently covers."
    else:
        reason = f"'{query}' isn't a valid 6-digit PIN code."
    raise LocationNotRecognized(query, suggestions, reason=reason)


def get_population(location_id: str) -> dict:
    """Population/catchment-default figures for a resolved location."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM population WHERE location_id = %s", (location_id,))
        row = cur.fetchone()
    if not row:
        raise LocationNotFound(f"No population record for location_id '{location_id}'")
    return dict(row)
