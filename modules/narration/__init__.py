"""
Narration layer — slot-filling, not post-filtering (project reference
§4.6). Server-side templates hold {{placeholders}}; real values are
interpolated in. `reject_if_contains_digit` is the guard a real LLM
integration must run its own free-text output through before it ever
reaches interpolation — in production an LLM would draft the connective
prose around these slots, and any digit it emits outside a
{{placeholder}} is rejected per R3, never silently kept.

This stage ships the deterministic English template path (server-only,
`render()` below) end to end and correct; wiring an actual LLM in for
paraphrase/multilingual is a later integration, using the same guard.
"""

import re
from decimal import Decimal

RAW_DIGIT_PATTERN = re.compile(r"\d")


def reject_if_contains_digit(llm_output: str) -> str:
    """Guard for a future LLM narration pass (R3): its free-text output —
    before slot interpolation — must not contain a raw digit. Not invoked
    by render() below, which is template-only and has no free-text LLM
    component yet."""
    if RAW_DIGIT_PATTERN.search(llm_output):
        raise ValueError("LLM narration output contains a raw digit — rejected per R3")
    return llm_output


def _inr(value) -> str:
    return f"Rs.{Decimal(str(value)):,.2f}"


def render(report_object, language: str = "en") -> str:
    """Deterministic English narration of a completed ReportObject.
    Multilingual is out of scope until Bhashini/AI4Bharat is wired in
    (project reference §6.1) — non-'en' currently falls back to English."""
    r = report_object
    loc = r.location
    lines = [
        f"ARTHA SETU feasibility & financial structuring report ({r.report_id})",
        f"Generated {r.generated_at} against data snapshot '{r.data_snapshot_version}'.",
        "",
        f"Location: {loc.get('village', '?')}, {loc.get('block', '?')}, {loc.get('district', '?')} "
        f"({loc.get('urban_rural_flag', '?')}).",
    ]

    if not r.eligibility.get("passed", False):
        lines.append("")
        lines.append("ELIGIBILITY: NOT MET. Reasons:")
        for reason in r.eligibility.get("reasons", []):
            lines.append(f"  - {reason}")
        lines.append("")
        lines.append("This applicant cannot proceed under this scheme. No financial or "
                      "feasibility figures were computed.")
        return "\n".join(lines)

    fs = r.financial_structuring
    lines += [
        "",
        "FINANCIAL STRUCTURING (borrow right, not borrow max):",
        f"  Recommended project cost: {_inr(fs['recommended_project_cost'])} "
        f"(operational need {_inr(fs['operational_project_cost'])}, "
        f"affordable ceiling {_inr(fs['affordable_max_project_cost'])}).",
        f"  Scheme: {fs['scheme']['scheme_key']} | Loan amount: {_inr(fs['scheme']['loan_amount'])} | "
        f"Margin required: {_inr(fs['scheme']['margin_required'])} | "
        f"Interest: {fs['scheme']['interest_rate_pct']}% p.a.",
        f"  {fs['note']}",
    ]

    fe = r.feasibility
    lines += [
        "",
        "FEASIBILITY:",
        f"  5km catchment population: {fe['catchment_population_5km']:,} | "
        f"10km: {fe['catchment_population_10km']:,}.",
        f"  {fe['competitor_count']} competitor(s) nearby, nearest at {fe['nearest_competitor_km']}km. "
        f"Demand gap {fe['demand_gap_pct']}%, classified {fe['opportunity_class']}.",
        f"  Estimated monthly revenue: {_inr(fe['estimated_monthly_revenue']['value'])} "
        f"[{_inr(fe['estimated_monthly_revenue']['low'])} - {_inr(fe['estimated_monthly_revenue']['high'])}].",
        "  SWOT:",
    ]
    for bullet in fe["swot"]:
        lines.append(f"    [{bullet['dimension'].upper()}] {bullet['description']}")

    rv = r.repayment_viability
    lines += [
        "",
        "REPAYMENT & VIABILITY:",
        f"  Moratorium mode: {rv['moratorium_mode']} | Quarterly installment (post-moratorium): "
        f"{_inr(rv['quarterly_installment'])}.",
        f"  {rv['verdict']}.",
    ]
    return "\n".join(lines)
