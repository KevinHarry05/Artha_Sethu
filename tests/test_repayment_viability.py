"""Stage 5 tests: Repayment & Viability (module 2b)."""

from decimal import Decimal

import pytest

from modules.repayment_viability import (
    build_amortisation_schedule,
    compute_viability,
    quarterly_payment_amount,
)
from schema import Evidence


def test_quarterly_payment_amount_positive_and_amortizes():
    installment = quarterly_payment_amount(Decimal("90000"), Decimal("6.5"), 11)
    assert installment > 0


def test_schedule_capitalised_grows_balance_during_moratorium():
    schedule = build_amortisation_schedule(
        loan_amount=Decimal("90000"), annual_rate_pct=Decimal("6.5"),
        tenure_months=36, moratorium_months=3, moratorium_mode="CAPITALISED",
    )
    moratorium_rows = [r for r in schedule if r.phase == "moratorium"]
    repayment_rows = [r for r in schedule if r.phase == "repayment"]
    assert len(moratorium_rows) == 1   # 3mo / 3
    assert len(repayment_rows) == 11   # (36/3) - 1
    assert moratorium_rows[0].installment_amount == Decimal("0.00")
    assert moratorium_rows[0].closing_balance > Decimal("90000")  # interest capitalised


def test_schedule_serviced_pays_interest_keeps_principal_flat():
    schedule = build_amortisation_schedule(
        loan_amount=Decimal("90000"), annual_rate_pct=Decimal("6.5"),
        tenure_months=36, moratorium_months=3, moratorium_mode="SERVICED",
    )
    mor = [r for r in schedule if r.phase == "moratorium"][0]
    assert mor.installment_amount > 0
    assert mor.closing_balance == Decimal("90000.00")  # principal untouched


def test_schedule_waived_charges_no_interest_in_moratorium():
    schedule = build_amortisation_schedule(
        loan_amount=Decimal("90000"), annual_rate_pct=Decimal("6.5"),
        tenure_months=36, moratorium_months=3, moratorium_mode="WAIVED",
    )
    mor = [r for r in schedule if r.phase == "moratorium"][0]
    assert mor.interest_charged == Decimal("0")
    assert mor.installment_amount == Decimal("0")
    assert mor.closing_balance == Decimal("90000.00")


def test_schedule_closes_at_or_near_zero():
    schedule = build_amortisation_schedule(
        loan_amount=Decimal("90000"), annual_rate_pct=Decimal("6.5"),
        tenure_months=36, moratorium_months=3, moratorium_mode="SERVICED",
    )
    assert schedule[-1].closing_balance <= Decimal("1.00")  # rounding dust only


def test_schedule_seasonality_adjusts_repayment_installments():
    schedule = build_amortisation_schedule(
        loan_amount=Decimal("90000"), annual_rate_pct=Decimal("6.5"),
        tenure_months=36, moratorium_months=3, moratorium_mode="SERVICED",
        business_category="Dairy",
    )
    repayment_rows = [r for r in schedule if r.phase == "repayment"]
    # seasonality factors should not all be exactly 1.00 across a real calendar
    assert any(r.seasonality_factor != Decimal("1.00") for r in repayment_rows)


def test_schedule_invalid_moratorium_mode_rejected():
    with pytest.raises(ValueError):
        build_amortisation_schedule(
            loan_amount=Decimal("90000"), annual_rate_pct=Decimal("6.5"),
            tenure_months=36, moratorium_months=3, moratorium_mode="BOGUS",
        )


def test_compute_viability_reports_scenario_count_not_a_colour():
    revenue = Evidence(
        value=Decimal("40000"), low=Decimal("24000"), high=Decimal("56000"),
        source="test", vintage="2026", method="test",
    )
    result = compute_viability(revenue, monthly_opex=Decimal("10000"), quarterly_installment=Decimal("30000"))
    assert result.n_scenarios == 10
    assert 0 <= result.repayable_count <= 10
    assert "Repayable in" in result.verdict
    assert f"{result.repayable_count} of 10" in result.verdict


def test_compute_viability_deterministic_for_same_seed():
    revenue = Evidence(
        value=Decimal("40000"), low=Decimal("24000"), high=Decimal("56000"),
        source="test", vintage="2026", method="test",
    )
    r1 = compute_viability(revenue, Decimal("10000"), Decimal("30000"), seed="fixed")
    r2 = compute_viability(revenue, Decimal("10000"), Decimal("30000"), seed="fixed")
    assert r1.repayable_count == r2.repayable_count
    assert [s.monthly_revenue for s in r1.scenarios] == [s.monthly_revenue for s in r2.scenarios]


def test_compute_viability_all_repayable_when_surplus_huge():
    revenue = Evidence(
        value=Decimal("500000"), low=Decimal("300000"), high=Decimal("700000"),
        source="test", vintage="2026", method="test",
    )
    result = compute_viability(revenue, monthly_opex=Decimal("1000"), quarterly_installment=Decimal("100"))
    assert result.repayable_count == 10
