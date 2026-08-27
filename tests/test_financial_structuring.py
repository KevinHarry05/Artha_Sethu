"""Stage 3 tests: Financial Structuring (module 2a) against the real NSFDC scheme."""

from decimal import Decimal

import pytest

from modules.financial_structuring import (
    OutOfSchemeError,
    get_project_cost_components,
    route_scheme,
    solve_max_project_cost,
    solve_required_margin,
)


def test_route_micro_credit_finance_below_cap_threshold():
    route = route_scheme(Decimal("100000"))
    assert route.scheme_key == "micro_credit_finance"
    assert route.loan_amount == Decimal("90000.00")   # 90% not yet capped
    assert not route.cap_bound
    assert route.margin_required == Decimal("10000.00")


def test_route_caps_override_percentage_at_140k():
    # Reference doc §2.5 item 3: at ₹1.40L, 90% = ₹1.26L but cap = ₹1.25L,
    # so required margin is ₹15,000, not ₹14,000.
    route = route_scheme(Decimal("140000"))
    assert route.scheme_key == "micro_credit_finance"
    assert route.loan_amount == Decimal("125000.00")
    assert route.cap_bound
    assert route.margin_required == Decimal("15000.00")


def test_route_term_loan_cap_exact_at_50l():
    route = route_scheme(Decimal("5000000"))
    assert route.scheme_key == "term_loan"
    assert route.loan_amount == Decimal("4500000.00")
    assert route.margin_required == Decimal("500000.00")


def test_route_out_of_scheme_above_50l():
    with pytest.raises(OutOfSchemeError):
        route_scheme(Decimal("5000001"))


def test_route_plantation_moratorium_exception():
    route = route_scheme(Decimal("500000"), activity="plantation")
    assert route.moratorium_months == 12


def test_solve_max_project_cost_affordable_matches_naive_when_uncapped():
    result = solve_max_project_cost(Decimal("10000"))  # well inside micro tier, no cap bind
    assert result.naive_max_project_cost == Decimal("100000.00")
    assert result.affordable_max_project_cost == result.naive_max_project_cost


def test_solve_max_project_cost_flags_naive_overstatement_near_cap():
    # margin of ₹14,000 naively implies a ₹1,40,000 project — but at that
    # cost the cap forces margin_required to ₹15,000, which this applicant
    # doesn't have. The affordable figure must come in below the naive one.
    result = solve_max_project_cost(Decimal("14000"))
    assert result.naive_max_project_cost == Decimal("140000.00")
    assert result.affordable_max_project_cost < result.naive_max_project_cost
    assert result.route.margin_required <= Decimal("14000")


def test_solve_required_margin_reverse_calc():
    result = solve_required_margin(Decimal("300000"))
    assert result.naive_required_margin == Decimal("30000.00")
    assert result.route.scheme_key == "term_loan"
    assert result.route.margin_required == Decimal("30000.00")  # not cap-bound at 3L


def test_solve_required_margin_reports_shortfall():
    result = solve_required_margin(Decimal("300000"), margin_available=Decimal("20000"))
    assert result.shortfall == Decimal("10000.00")


def test_get_project_cost_components_dairy_matches_dataset():
    # From 04_business_cost_profiles.csv: capex 32000+75000+15000=122000,
    # working capital 3000*3=9000 -> matches 08_module1_feasibility_assessment.csv rows.
    comp = get_project_cost_components("Dairy")
    assert comp["capex"] == Decimal("122000.00")
    assert comp["working_capital"] == Decimal("9000.00")
    assert comp["operational_project_cost"] == Decimal("131000.00")
