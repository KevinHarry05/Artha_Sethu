"""
On-demand synthetic data generation for any location that isn't in the
curated 200-location Tamil Nadu dataset. This is what lets the pipeline
accept "Koramangala", "Bengaluru", "Rajasthan", or a made-up village name
and never error — at the honestly-disclosed cost that everything downstream
of an auto-generated location is illustrative, not sourced Census/EC data.

Deterministic (random.Random seeded by location_id — same query always
regenerates the same numbers) and idempotent (a location, once synthesized,
is written to the DB once and reused on every later call).

AUTO_DATA_SOURCE is the tag every auto-generated row carries so a judge
question ("where did that number come from?") gets an honest answer, never
a silently-invented one dressed up as EC 2013 / Census / HCES.
"""

import hashlib
import random
from decimal import ROUND_HALF_UP, Decimal

from db.connection import get_cursor
from modules.location_resolver.gazetteer import INDIAN_STATES, LOCALITY_TO_CITY, MAJOR_CITIES

AUTO_DATA_SOURCE = "auto_generated_synthetic_no_ground_truth (unrecognized location, illustrative estimate)"
CATEGORIES = ["Dairy", "Retail", "Textiles"]
PRODUCT_BY_CATEGORY = {
    "Dairy": ("milk", 32.5), "Retail": ("grocery_staples_basket", 150.0), "Textiles": ("stitched_garment", 400.0),
}

POPULATION_RANGE_BY_TIER = {
    "urban": (50000, 300000), "peri-urban": (15000, 50000), "rural-other": (2000, 10000),
}
DEFAULT_COMPETITOR_COUNT = {
    "urban": {"Dairy": 6, "Retail": 14, "Textiles": 5},
    "peri-urban": {"Dairy": 4, "Retail": 9, "Textiles": 3},
    "rural-other": {"Dairy": 2, "Retail": 4, "Textiles": 1},
}
DEFAULT_NEAREST_KM = {"urban": 0.8, "peri-urban": 1.5, "rural-other": 3.0}


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _location_id_for(query: str) -> str:
    digest = hashlib.md5(query.strip().lower().encode()).hexdigest()[:10]
    return f"auto_{digest}"


def resolve_candidate(query: str) -> dict:
    """Chains locality -> city -> state gazetteer lookups; falls back to
    treating the raw query as a new, otherwise-unplaced district. Never
    raises — this is the function that guarantees 'any state, any locality,
    no error'."""
    q = " ".join(query.strip().lower().split())

    if q in LOCALITY_TO_CITY:
        city_key = LOCALITY_TO_CITY[q]
        city_name, state, district, lat, lon = MAJOR_CITIES[city_key]
        return dict(village=query.strip().title(), block=city_name, district=district, state=state,
                    region=state, lat=lat, lon=lon, tier="urban", resolution="gazetteer_locality")

    if q in MAJOR_CITIES:
        city_name, state, district, lat, lon = MAJOR_CITIES[q]
        return dict(village=f"{city_name} (city centre, auto)", block=city_name, district=district,
                    state=state, region=state, lat=lat, lon=lon, tier="urban", resolution="gazetteer_city")

    if q in INDIAN_STATES:
        capital, district, lat, lon = INDIAN_STATES[q]
        return dict(village=f"{capital} (state capital fallback, auto)", block=capital, district=district,
                    state=query.strip().title(), region=query.strip().title(), lat=lat, lon=lon,
                    tier="urban", resolution="gazetteer_state_capital")

    # Final catch-all: nothing recognized at all. Deterministically place it
    # somewhere within India's bounding box, seeded by the query text, and
    # say so plainly rather than guessing a real place.
    rng = random.Random(f"unresolved_{q}")
    lat = round(rng.uniform(8.0, 34.0), 4)
    lon = round(rng.uniform(69.0, 96.0), 4)
    return dict(village=query.strip().title(), block=f"{query.strip().title()} (auto)",
                district=query.strip().title(), state="Unrecognized (auto-placed, not geocoded)",
                region="Unrecognized (auto-placed, not geocoded)", lat=lat, lon=lon,
                tier="rural-other", resolution="unresolved_freeform")


def ensure_location_exists(query: str) -> dict:
    """Idempotent: if this query has already been synthesized, returns the
    existing DB row; otherwise resolves a candidate via the gazetteer chain,
    inserts villages/population/competitors/market_prices rows for it, and
    returns the new row. Downstream modules never need to know whether a
    location came from the curated dataset or from here."""
    location_id = _location_id_for(query)

    with get_cursor() as cur:
        cur.execute("SELECT * FROM villages WHERE location_id = %s", (location_id,))
        existing = cur.fetchone()
    if existing:
        return dict(existing)

    candidate = resolve_candidate(query)
    tier = candidate["tier"]
    rng = random.Random(location_id)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO villages (location_id, lgd_code, village, block, district, region, state,
                                   latitude, longitude, urban_rural_flag, data_source, data_vintage_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, CURRENT_DATE)
            """,
            (location_id, f"AUTO-{location_id[5:].upper()}", candidate["village"], candidate["block"],
             candidate["district"], candidate["region"], candidate["state"], candidate["lat"],
             candidate["lon"], tier, AUTO_DATA_SOURCE),
        )

        pop_lo, pop_hi = POPULATION_RANGE_BY_TIER[tier]
        population = rng.randint(pop_lo, pop_hi)
        households = int(population / 4.3)
        cur.execute(
            """
            INSERT INTO population (location_id, population_2011, households_2011,
                                     catchment_population_default, sc_st_percent,
                                     below_poverty_line_percent, data_source, data_vintage_date, confidence_flag)
            VALUES (%s,%s,%s,%s,%s,%s,%s, CURRENT_DATE, %s)
            """,
            (location_id, population, households, population, round(rng.uniform(10, 30), 1),
             round(rng.uniform(15, 35), 1), AUTO_DATA_SOURCE, "auto_generated_no_survey"),
        )

        for cat in CATEGORIES:
            base_count = DEFAULT_COMPETITOR_COUNT[tier][cat]
            count = max(0, base_count + rng.randint(-1, 1))
            nearest_km = max(0.1, round(DEFAULT_NEAREST_KM[tier] + rng.uniform(-0.4, 0.4), 2))
            cur.execute(
                """
                INSERT INTO competitors (location_id, business_category, competitor_count,
                                          nearest_competitor_km, data_source)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (location_id, business_category) DO NOTHING
                """,
                (location_id, cat, count, nearest_km, AUTO_DATA_SOURCE),
            )

        # District-level market prices — only insert if this district has none yet.
        for cat in CATEGORIES:
            product, base_price = PRODUCT_BY_CATEGORY[cat]
            cur.execute(
                "SELECT 1 FROM market_prices WHERE district = %s AND product = %s",
                (candidate["district"], product),
            )
            if cur.fetchone():
                continue
            district = candidate["district"]
            price_rng = random.Random(f"price_{district}_{cat}")
            variance = round(price_rng.uniform(0.92, 1.08), 3)
            modal = money(Decimal(str(base_price)) * Decimal(str(variance)))
            market_id_seed = f"{district}_{product}"
            market_id = "mrkt_auto_" + hashlib.md5(market_id_seed.encode()).hexdigest()[:8]
            cur.execute(
                """
                INSERT INTO market_prices (market_id, product, district, region, price_modal_inr,
                                            price_min_inr, price_max_inr, price_unit, price_date,
                                            price_source, data_vintage_days_ago)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s, CURRENT_DATE, %s, 0)
                """,
                (market_id, product, candidate["district"], candidate["region"], modal,
                 money(modal * Decimal("0.92")), money(modal * Decimal("1.08")), "per unit",
                 AUTO_DATA_SOURCE),
            )

    with get_cursor() as cur:
        cur.execute("SELECT * FROM villages WHERE location_id = %s", (location_id,))
        return dict(cur.fetchone())
