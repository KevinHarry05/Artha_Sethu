"""
Wires modules 0 -> gate -> 2a -> 1 -> 2b into the single pipeline call the
architecture diagram describes, and assembles the Report Object (§4.7).

This is the orchestration layer only — every number in here was already
computed by a module; this file just calls them in the right order, passes
budget tier down into feasibility and expected revenue down into
repayment, and records a calculation trace (R6) as it goes.
"""

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

from modules.feasibility_engine import (
    assemble_swot,
    build_catchment,
    build_risk_flags,
    estimate_demand,
    opportunity_class_from_gap,
)
from modules.financial_structuring import (
    get_project_cost_components,
    route_scheme,
    solve_max_project_cost,
)
from modules.location_resolver import resolve_location
from modules.pre_screening_gate import check_eligibility
from modules.repayment_viability import build_amortisation_schedule, compute_viability
from schema import ReportObject, TraceStep

DATA_SNAPSHOT_VERSION = "makeathon_internal_synthetic_v1_200loc"


def run_pipeline(
    location_query: str,
    business_category: str,
    margin_available: Decimal,
    community: str,
    annual_family_income_inr: Decimal,
    is_defaulter: bool,
    activity: str = "",
    moratorium_mode: str = "SERVICED",
) -> ReportObject:
    report_id = f"rpt_{uuid.uuid4().hex[:12]}"
    generated_at = datetime.now(timezone.utc).isoformat()
    trace: list[TraceStep] = []

    # [0] LOCATION RESOLVER
    loc = resolve_location(location_query)
    trace.append(TraceStep(
        step="location_resolver", inputs={"query": location_query}, formula="DB lookup (exact/fuzzy)",
        output=loc["location_id"], sources=[loc.get("data_source", "")],
    ))

    # [PRE-SCREENING GATE]
    eligibility = check_eligibility(community, float(annual_family_income_inr), is_defaulter)
    trace.append(TraceStep(
        step="pre_screening_gate",
        inputs={"community": community, "income": str(annual_family_income_inr), "is_defaulter": is_defaulter},
        formula="community match AND income < ceiling AND NOT is_defaulter",
        output=eligibility.passed, sources=["config/scheme_config.yaml"],
    ))

    report = ReportObject(
        report_id=report_id, data_snapshot_version=DATA_SNAPSHOT_VERSION, generated_at=generated_at,
        location=dict(loc), eligibility={"passed": eligibility.passed, "reasons": eligibility.reasons},
    )

    if not eligibility.passed:
        report.trace = trace
        return report  # scope ends here — never route/compute finance for an ineligible applicant

    # [2a] FINANCIAL STRUCTURING
    components = get_project_cost_components(business_category)
    max_result = solve_max_project_cost(margin_available, activity=activity)
    recommended_project_cost = min(max_result.affordable_max_project_cost, components["operational_project_cost"])
    route = route_scheme(recommended_project_cost, activity=activity)
    trace.append(TraceStep(
        step="financial_structuring",
        inputs={"margin_available": str(margin_available), "category": business_category},
        formula="recommended_cost = MIN(affordable_max_project_cost, operational_project_cost); "
                "borrow right, not borrow max",
        output={"recommended_project_cost": str(recommended_project_cost), "loan_amount": str(route.loan_amount)},
        sources=["config/scheme_config.yaml", "04_business_cost_profiles.csv (NABARD-illustrative)"],
    ))
    report.financial_structuring = {
        "naive_max_project_cost": max_result.naive_max_project_cost,
        "affordable_max_project_cost": max_result.affordable_max_project_cost,
        "operational_project_cost": components["operational_project_cost"],
        "recommended_project_cost": recommended_project_cost,
        "capex": components["capex"], "working_capital": components["working_capital"],
        "note": max_result.note, "scheme": asdict(route),
    }

    # [1] FEASIBILITY ENGINE (budget-aware: knows the scheme tier now)
    demand = estimate_demand(loc["location_id"], business_category, loc["district"], loc["urban_rural_flag"])
    catchment_5km = build_catchment(loc["location_id"], radius_km=5)
    catchment_10km = build_catchment(loc["location_id"], radius_km=10)
    risk = build_risk_flags(business_category, demand.nearest_competitor_km)
    swot = assemble_swot(
        business_category, demand, risk["risk_severity_score"], route.scheme_key,
        route.project_cost, components["capex"],
    )
    opp_class = opportunity_class_from_gap(demand.demand_gap_pct, demand.competitor_count)
    trace.append(TraceStep(
        step="feasibility_engine",
        inputs={"location_id": loc["location_id"], "category": business_category},
        formula="demand_gap = 100*(1-c/(c+5)); revenue = units*30*price, +/-40% band",
        output={"competitor_count": demand.competitor_count, "demand_gap_pct": str(demand.demand_gap_pct)},
        sources=["09/08_...csv (competitor counts)", "05_market_prices.csv"],
    ))
    report.feasibility = {
        "catchment_population_5km": catchment_5km.value, "catchment_population_10km": catchment_10km.value,
        "competitor_count": demand.competitor_count, "nearest_competitor_km": demand.nearest_competitor_km,
        "demand_gap_pct": demand.demand_gap_pct, "price_modal_inr": demand.price_modal_inr,
        "estimated_monthly_revenue": {
            "value": demand.estimated_monthly_revenue.value, "low": demand.estimated_monthly_revenue.low,
            "high": demand.estimated_monthly_revenue.high,
        },
        "opportunity_class": opp_class, "risk": risk, "swot": swot,
    }

    # [2b] REPAYMENT & VIABILITY (needs module 1's expected revenue)
    schedule = build_amortisation_schedule(
        loan_amount=route.loan_amount, annual_rate_pct=route.interest_rate_pct,
        tenure_months=route.tenure_months, moratorium_months=route.moratorium_months,
        moratorium_mode=moratorium_mode, business_category=business_category,
    )
    repayment_rows = [r for r in schedule if r.phase == "repayment"]
    quarterly_installment = repayment_rows[0].installment_amount if repayment_rows else Decimal(0)
    monthly_opex = components["working_capital"] / Decimal(3)
    viability = compute_viability(
        demand.estimated_monthly_revenue, monthly_opex, quarterly_installment,
        seed=f"{loc['location_id']}_{business_category}",
    )
    trace.append(TraceStep(
        step="repayment_viability",
        inputs={"loan_amount": str(route.loan_amount), "moratorium_mode": moratorium_mode},
        formula="quarterly amortisation, declining balance; viability = scenario sampling over revenue/cost bands",
        output=viability.verdict, sources=["06_seasonality_profile.csv"],
    ))
    report.repayment_viability = {
        "quarterly_installment": quarterly_installment, "monthly_opex": monthly_opex,
        "schedule_length": len(schedule), "moratorium_mode": moratorium_mode,
        "verdict": viability.verdict, "repayable_count": viability.repayable_count,
        "n_scenarios": viability.n_scenarios,
        "total_repayment": sum((r.installment_amount for r in repayment_rows), Decimal(0)),
    }

    report.trace = trace
    return report
