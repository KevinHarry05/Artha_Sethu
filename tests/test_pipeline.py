"""Stage 6 tests: full pipeline (0 -> gate -> 2a -> 1 -> 2b -> report + narration)."""

from decimal import Decimal

import pytest

from modules.narration import reject_if_contains_digit, render
from modules.narration.render_html import render_html
from pipeline import run_pipeline


def test_pipeline_eligible_applicant_end_to_end():
    # Mirrors app_CGP_DAI: Chengalpattu Dairy, ~Rs.15,000 margin.
    report = run_pipeline(
        location_query="loc_CGP_05", business_category="Dairy", margin_available=Decimal("15000"),
        community="SC", annual_family_income_inr=Decimal("120000"), is_defaulter=False,
    )
    assert report.eligibility["passed"]
    assert report.financial_structuring["recommended_project_cost"] > 0
    assert report.financial_structuring["scheme"]["loan_amount"] > 0
    assert report.feasibility["competitor_count"] >= 0
    assert len(report.feasibility["swot"]) == 5
    assert report.repayment_viability["n_scenarios"] == 10
    assert "Repayable in" in report.repayment_viability["verdict"]
    assert len(report.trace) == 5  # location, gate, 2a, 1, 2b


def test_pipeline_ineligible_applicant_stops_before_finance():
    report = run_pipeline(
        location_query="loc_CGP_01", business_category="Retail", margin_available=Decimal("26475"),
        community="OBC", annual_family_income_inr=Decimal("120000"), is_defaulter=False,
    )
    assert not report.eligibility["passed"]
    assert report.financial_structuring == {}   # scope ends at the gate
    assert report.feasibility == {}
    assert len(report.trace) == 2  # location, gate only


def test_pipeline_defaulter_stops_at_gate():
    report = run_pipeline(
        location_query="loc_CGP_01", business_category="Dairy", margin_available=Decimal("15000"),
        community="SC", annual_family_income_inr=Decimal("100000"), is_defaulter=True,
    )
    assert not report.eligibility["passed"]
    assert any("default" in r.lower() for r in report.eligibility["reasons"])


def test_narration_renders_eligible_report():
    report = run_pipeline(
        location_query="loc_CGP_05", business_category="Dairy", margin_available=Decimal("15000"),
        community="SC", annual_family_income_inr=Decimal("120000"), is_defaulter=False,
    )
    text = render(report)
    assert "FINANCIAL STRUCTURING" in text
    assert "FEASIBILITY" in text
    assert "REPAYMENT & VIABILITY" in text
    assert report.report_id in text


def test_narration_renders_ineligible_report_short_circuits():
    report = run_pipeline(
        location_query="loc_CGP_01", business_category="Retail", margin_available=Decimal("26475"),
        community="OBC", annual_family_income_inr=Decimal("120000"), is_defaulter=False,
    )
    text = render(report)
    assert "ELIGIBILITY: NOT MET" in text
    assert "FINANCIAL STRUCTURING" not in text


def test_reject_if_contains_digit_guard():
    assert reject_if_contains_digit("no numbers here") == "no numbers here"
    with pytest.raises(ValueError):
        reject_if_contains_digit("the revenue is 4000 rupees")


def test_render_html_embeds_trace_table():
    report = run_pipeline(
        location_query="loc_CGP_05", business_category="Dairy", margin_available=Decimal("15000"),
        community="SC", annual_family_income_inr=Decimal("120000"), is_defaulter=False,
    )
    html = render_html(report)
    assert "<table>" in html
    assert report.report_id in html
    assert "location_resolver" in html
