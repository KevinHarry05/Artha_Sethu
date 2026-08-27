"""Stage 4 tests: Feasibility Engine (module 1) against real Postgres data."""

from decimal import Decimal

from modules.feasibility_engine import (
    assemble_swot,
    build_catchment,
    build_risk_flags,
    demand_gap_pct,
    estimate_demand,
    get_competitors,
    get_price,
    opportunity_class_from_gap,
)


def test_build_catchment_includes_self_and_caches():
    ev = build_catchment("loc_CGP_01", radius_km=5)
    assert ev.value > 0
    assert "5km" in ev.method
    # second call should hit the cache and return the same value
    ev2 = build_catchment("loc_CGP_01", radius_km=5)
    assert ev2.value == ev.value


def test_build_catchment_10km_covers_at_least_as_much_as_5km():
    ev5 = build_catchment("loc_CGP_02", radius_km=5)
    ev10 = build_catchment("loc_CGP_02", radius_km=10)
    assert ev10.value >= ev5.value


def test_get_competitors_dairy_chengalpattu_01():
    ev = get_competitors("loc_CGP_01", "Dairy")
    assert ev.value == 6   # matches 08_module1_feasibility_assessment.csv feas_0001


def test_demand_gap_pct_matches_generator_formula():
    # feas_0001: 6 competitors -> demand_gap 45.45 per the dataset
    assert demand_gap_pct(6) == Decimal("45.45")


def test_get_price_applies_tier_variance():
    ev = get_price("Chengalpattu", "Dairy", "urban")
    assert ev.value > 0
    assert ev.low < ev.value < ev.high


def test_estimate_demand_produces_interval_evidence():
    d = estimate_demand("loc_CGP_01", "Dairy", "Chengalpattu", "urban")
    assert d.competitor_count == 6
    rev = d.estimated_monthly_revenue
    assert rev.low < rev.value < rev.high
    # +/-40% band per R2
    assert rev.low == rev.value - (rev.value * Decimal("0.40"))


def test_build_risk_flags_returns_category_factors():
    flags = build_risk_flags("Dairy", nearest_competitor_km=Decimal("1.22"))
    assert "seasonality_monsoon_lean" in flags["key_risk_factors"]
    assert flags["risk_severity_score"] == Decimal("4.5")


def test_assemble_swot_every_bullet_cites_a_number():
    d = estimate_demand("loc_CGP_01", "Dairy", "Chengalpattu", "urban")
    bullets = assemble_swot(
        "Dairy", d, risk_severity=Decimal("4.5"), scheme_tier="micro_credit_finance",
        project_cost=Decimal("131000"), capex=Decimal("122000"),
    )
    assert len(bullets) == 5  # 4 base dimensions + 1 budget-dependent
    for b in bullets:
        assert any(ch.isdigit() for ch in b["description"])  # R5: cites a computed number


def test_assemble_swot_flips_budget_bullet_by_tier():
    d = estimate_demand("loc_CGP_01", "Dairy", "Chengalpattu", "urban")
    micro = assemble_swot("Dairy", d, Decimal("4.5"), "micro_credit_finance", Decimal("131000"), Decimal("122000"))
    term = assemble_swot("Dairy", d, Decimal("4.5"), "term_loan", Decimal("300000"), Decimal("250000"))
    assert micro[-1]["dimension"] == "weakness"
    assert term[-1]["dimension"] == "strength"


def test_opportunity_class_from_gap():
    assert opportunity_class_from_gap(Decimal("80"), 2) == "underserved"
    assert opportunity_class_from_gap(Decimal("50"), 5) == "balanced"
    assert opportunity_class_from_gap(Decimal("20"), 10) == "saturated"
