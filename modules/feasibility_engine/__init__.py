"""
[1] FEASIBILITY ENGINE (budget-aware — needs module 2a's scheme tier/capex).

Sub-components (project reference §4.4):
  - Catchment builder    5/10 km buffer, precomputed and cached (R1)
  - Competitor counter    from `competitors` table (see db/ingest_raw_data.py
                           docstring for why this is treated as raw input)
  - Demand estimator      competitor-density heuristic — see note below
  - Price engine          district market price x location-tier variance
  - Risk tagger           rule-based flags, per category
  - SWOT assembler        every bullet cites a computed number (R5),
                           budget-tier-aware (reference §2.5 item 9)

Demand estimator note: the project reference's target design is
catchment_population x HCES per-capita spend / competitors — but no HCES
table has been ingested yet (not present in this synthetic dataset). Until
that data lands, demand is estimated via the competitor-density heuristic
below (reproduced from generate_synthetic_dataset_scaled.py's formula
shape — see docs/DATA_DECISIONS.md). DemandProvider is a swappable function
so switching to the HCES formula later is a config/data change, not a
rewrite.

All Evidence-returning per the schema/evidence.py data contract — no bare
floats leave this module.
"""

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from db.connection import get_cursor
from schema import Evidence

TWO_DP = Decimal("0.01")


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Category content — reproduced from the dataset's generator script.
# NABARD/field-survey-illustrative in origin (synthetic at this stage).
# Per R8, this is content, not code: whoever owns activity templates should
# review these alongside 04_business_cost_profiles.csv before the real demo.
# ---------------------------------------------------------------------------
PRODUCT_BY_CATEGORY = {
    "Dairy": dict(product="milk", unit="per litre"),
    "Retail": dict(product="grocery_staples_basket", unit="per transaction"),
    "Textiles": dict(product="stitched_garment", unit="per garment"),
}
PRICE_VARIANCE_BY_TIER = {
    "urban": Decimal("1.06"), "peri-urban": Decimal("1.00"),
    "rural-temple-town": Decimal("0.99"), "rural-agri": Decimal("0.94"),
    "rural-other": Decimal("0.96"),
}
BASE_DAILY_UNITS = {"Dairy": Decimal(24), "Retail": Decimal(15), "Textiles": Decimal(4)}
BASE_RISK_SEVERITY = {"Dairy": Decimal("4.5"), "Retail": Decimal("4.0"), "Textiles": Decimal("3.5")}
RISK_FACTORS_BY_CATEGORY = {
    "Dairy": ["seasonality_monsoon_lean", "fodder_price_volatility", "animal_health_risk"],
    "Retail": ["inventory_spoilage_perishables", "competitor_price_undercutting", "credit_sales_default"],
    "Textiles": ["raw_material_price_volatility", "seasonal_demand_concentration", "skill_dependency_single_artisan"],
}
SWOT_TEMPLATES = {
    "Dairy": dict(
        strength="Established local demand for fresh milk; low competitor density outside urban core.",
        weakness="Revenue drops materially in monsoon months due to lower milk yield.",
        opportunity="Dairy cooperative offtake nearby offers guaranteed procurement and price floor.",
        threat="Regional livestock disease risk with limited veterinary infrastructure.",
    ),
    "Retail": dict(
        strength="High household density near market centers supports steady daily footfall.",
        weakness="Thin margins make the business highly sensitive to competitor price undercutting.",
        opportunity="Festival season demand spikes are predictable and plannable for.",
        threat="Larger organized retail or wholesale chains could enter and undercut on price.",
    ),
    "Textiles": dict(
        strength="Low capex entry point relative to other categories; flexible home-based operation.",
        weakness="Revenue heavily concentrated in wedding and festival seasons, thin in monsoon.",
        opportunity="Temple-town footfall and wedding season create bulk-order potential.",
        threat="Raw material (cotton/fabric) price volatility compresses margins unpredictably.",
    ),
}

DEMAND_UNCERTAINTY_PCT = Decimal("0.40")  # reference §4.5: demand carries +/-40% uncertainty


# ---------------------------------------------------------------------------
# Catchment builder
# ---------------------------------------------------------------------------
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_catchment(location_id: str, radius_km: int) -> Evidence:
    """5/10km catchment population, computed once and cached (R1 — no
    external call or O(n^2) recompute per request)."""
    if radius_km not in (5, 10):
        raise ValueError("radius_km must be 5 or 10 per the PS's stated bands")

    with get_cursor() as cur:
        cur.execute(
            "SELECT catchment_population, village_count FROM catchment_cache "
            "WHERE location_id = %s AND radius_km = %s",
            (location_id, radius_km),
        )
        cached = cur.fetchone()
        if cached:
            return Evidence(
                value=cached["catchment_population"], low=cached["catchment_population"],
                high=cached["catchment_population"],
                source="Census 2011 PCA (synthetic_illustrative_demo) via cached catchment buffer",
                vintage="2011", method=f"{radius_km}km haversine buffer, {cached['village_count']} villages",
            )

        cur.execute("SELECT latitude, longitude FROM villages WHERE location_id = %s", (location_id,))
        center = cur.fetchone()
        if not center:
            raise ValueError(f"Unknown location_id '{location_id}'")

        cur.execute(
            "SELECT v.location_id, v.latitude, v.longitude, p.catchment_population_default, "
            "p.households_2011 FROM villages v JOIN population p ON v.location_id = p.location_id"
        )
        all_villages = cur.fetchall()

    within = [
        v for v in all_villages
        if _haversine_km(center["latitude"], center["longitude"], v["latitude"], v["longitude"]) <= radius_km
    ]
    catchment_population = sum(v["catchment_population_default"] for v in within)
    catchment_households = sum(v["households_2011"] for v in within)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO catchment_cache (location_id, radius_km, catchment_population,
                                          catchment_households, village_count)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (location_id, radius_km) DO UPDATE SET
                catchment_population = EXCLUDED.catchment_population,
                catchment_households = EXCLUDED.catchment_households,
                village_count = EXCLUDED.village_count,
                computed_at = now()
            """,
            (location_id, radius_km, catchment_population, catchment_households, len(within)),
        )

    return Evidence(
        value=catchment_population, low=catchment_population, high=catchment_population,
        source="Census 2011 PCA (synthetic_illustrative_demo) — freshly computed catchment buffer",
        vintage="2011", method=f"{radius_km}km haversine buffer, {len(within)} villages",
    )


# ---------------------------------------------------------------------------
# Competitor counter
# ---------------------------------------------------------------------------
def get_competitors(location_id: str, business_category: str) -> Evidence:
    with get_cursor() as cur:
        cur.execute(
            "SELECT competitor_count, nearest_competitor_km, data_source FROM competitors "
            "WHERE location_id = %s AND business_category = %s",
            (location_id, business_category),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"No competitor data for ({location_id}, {business_category})")
    count = row["competitor_count"]
    return Evidence(
        value=count, low=max(0, count - 1), high=count + 1,   # +/-1 unit: block-level counts are approximate
        source=row["data_source"], vintage="2026", method="block-level establishment count",
    )


def demand_gap_pct(competitor_count: int) -> Decimal:
    """Reproduced from the generator: demand_gap = 100 x (1 - c/(c+5))."""
    c = Decimal(competitor_count)
    return money(Decimal(100) * (Decimal(1) - c / (c + Decimal(5))))


# ---------------------------------------------------------------------------
# Price engine
# ---------------------------------------------------------------------------
def get_price(district: str, business_category: str, urban_rural_flag: str) -> Evidence:
    product = PRODUCT_BY_CATEGORY[business_category]["product"]
    with get_cursor() as cur:
        cur.execute(
            "SELECT price_modal_inr, price_min_inr, price_max_inr, price_source, price_date "
            "FROM market_prices WHERE district = %s AND product = %s",
            (district, product),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"No price data for ({district}, {product})")

    tier_key = urban_rural_flag.replace("_", "-")
    variance = PRICE_VARIANCE_BY_TIER.get(tier_key, Decimal("1.00"))
    modal = money(Decimal(str(row["price_modal_inr"])) * variance)
    low = money(Decimal(str(row["price_min_inr"])) * variance)
    high = money(Decimal(str(row["price_max_inr"])) * variance)
    return Evidence(
        value=modal, low=low, high=high, source=row["price_source"],
        vintage=str(row["price_date"]), method=f"district modal price x {tier_key} tier variance",
    )


# ---------------------------------------------------------------------------
# Demand estimator
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DemandEstimate:
    competitor_count: int
    nearest_competitor_km: Decimal
    demand_gap_pct: Decimal
    price_modal_inr: Decimal
    estimated_daily_units: Decimal
    estimated_monthly_revenue: Evidence   # +/-40% interval per R2


def estimate_demand(location_id: str, business_category: str, district: str, urban_rural_flag: str) -> DemandEstimate:
    comp = get_competitors(location_id, business_category)
    price = get_price(district, business_category, urban_rural_flag)
    gap = demand_gap_pct(comp.value)

    base_units = BASE_DAILY_UNITS[business_category]
    effective_units = (base_units * (Decimal("0.7") + (gap / Decimal(100)) * Decimal("0.3"))).quantize(Decimal("0.1"))
    monthly_revenue = money(effective_units * Decimal(30) * Decimal(str(price.value)))

    band = monthly_revenue * DEMAND_UNCERTAINTY_PCT
    revenue_evidence = Evidence(
        value=monthly_revenue, low=money(monthly_revenue - band), high=money(monthly_revenue + band),
        source="derived: competitor-density demand heuristic x district price (HCES not yet ingested)",
        vintage="2026", method="demand_gap-weighted daily units x 30 x price_modal, +/-40% uncertainty band",
    )
    return DemandEstimate(
        competitor_count=comp.value, nearest_competitor_km=Decimal(str(comp.low)),
        demand_gap_pct=gap, price_modal_inr=Decimal(str(price.value)),
        estimated_daily_units=effective_units, estimated_monthly_revenue=revenue_evidence,
    )


# ---------------------------------------------------------------------------
# Risk tagger (rule-based)
# ---------------------------------------------------------------------------
def build_risk_flags(business_category: str, nearest_competitor_km: Decimal) -> dict:
    factors = list(RISK_FACTORS_BY_CATEGORY[business_category])
    if nearest_competitor_km > Decimal("15"):
        factors.append("distance_to_market_over_15km")
    return {
        "key_risk_factors": factors,
        "risk_severity_score": BASE_RISK_SEVERITY[business_category],
    }


# ---------------------------------------------------------------------------
# SWOT assembler — every bullet cites a computed number (R5)
# ---------------------------------------------------------------------------
def assemble_swot(
    business_category: str,
    demand: DemandEstimate,
    risk_severity: Decimal,
    scheme_tier: str,
    project_cost: Decimal,
    capex: Decimal,
) -> list[dict]:
    tpl = SWOT_TEMPLATES[business_category]
    bullets = [
        dict(dimension="strength", description=(
            f"{tpl['strength']} ({demand.competitor_count} competitor(s) within "
            f"{demand.nearest_competitor_km}km, demand gap {demand.demand_gap_pct}%.)"
        )),
        dict(dimension="weakness", description=(
            f"{tpl['weakness']} (Category risk severity {risk_severity}/10.)"
        )),
        dict(dimension="opportunity", description=(
            f"{tpl['opportunity']} (Demand gap of {demand.demand_gap_pct}% estimated from "
            f"{demand.competitor_count} local competitor(s).)"
        )),
        dict(dimension="threat", description=(
            f"{tpl['threat']} (Nearest competitor at {demand.nearest_competitor_km}km; "
            f"estimated monthly revenue Rs.{demand.estimated_monthly_revenue.value:,.2f} "
            f"[Rs.{demand.estimated_monthly_revenue.low:,.2f}-Rs.{demand.estimated_monthly_revenue.high:,.2f}].)"
        )),
    ]

    # Budget-dependent bullet — reference §2.5 item 9: SWOT is budget-dependent,
    # e.g. a chiller is unaffordable at the micro tier (weakness) but affordable
    # at the term-loan tier (strength). Grounded in this applicant's own
    # module-2a numbers, not an invented hardware cost.
    if scheme_tier == "micro_credit_finance":
        bullets.append(dict(dimension="weakness", description=(
            f"At the Micro Credit Finance tier (project cost capped near Rs.1,40,000; this "
            f"applicant's capex budget is Rs.{capex:,.2f}), infrastructure upgrades beyond the "
            f"baseline {business_category.lower()} setup are constrained by budget, not just by market."
        )))
    else:
        bullets.append(dict(dimension="strength", description=(
            f"At the {scheme_tier.replace('_', ' ').title()} tier (project cost Rs.{project_cost:,.2f}, "
            f"capex budget Rs.{capex:,.2f}), the applicant can invest beyond the baseline "
            f"{business_category.lower()} setup — a budget-driven strength distinct from the market-driven one above."
        )))

    return bullets


def opportunity_class_from_gap(gap_pct: Decimal, competitor_count: int) -> str:
    """Coarse, transparent classification — not the dataset's score formula,
    which mixes in risk/distance too (that lives in the feasibility score
    below, kept separate so each number's provenance stays inspectable)."""
    if competitor_count == 0:
        return "underserved"
    if gap_pct >= Decimal(70):
        return "underserved"
    if gap_pct >= Decimal(40):
        return "balanced"
    return "saturated"
