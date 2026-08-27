"""
[2b] REPAYMENT & VIABILITY — needs module 1's expected revenue and module
2a's loan terms.

Quarterly amortisation with three configurable moratorium interest modes
(config/scheme_config.yaml: CAPITALISED / SERVICED / WAIVED — reference
§2.5 item 5, unverified with an SCA, hence configurable rather than fixed).

Note on tenure vs. moratorium: the real NSFDC scheme states moratorium is
*included* in tenure ("3 years incl. 3-month moratorium" — reference §2.2),
unlike the synthetic dataset's generator script, which adds moratorium
quarters on top of the scheme's tenure_years. This module follows the real
scheme's semantics: repayment_quarters = total_quarters - moratorium_quarters.

Viability uses interval arithmetic, not a single verdict colour (R2):
demand carries the +/-40% band already attached to Evidence by the
Feasibility Engine; the cost model carries +/-25% (reference §4.5). A fixed
number of scenarios are sampled across both bands (deterministically
seeded, so the verdict is reproducible) and the report is
"repayable in N of {n_scenarios} scenarios".

Money is always Decimal (R4).
"""

import random
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from db.connection import get_cursor
from schema import Evidence

TWO_DP = Decimal("0.01")
COST_UNCERTAINTY_PCT = Decimal("0.25")  # reference §4.5: cost model carries +/-25%


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Quarterly amortisation
# ---------------------------------------------------------------------------
def quarterly_payment_amount(principal: Decimal, annual_rate_pct: Decimal, n_quarters: int) -> Decimal:
    """Standard amortizing annuity, declining balance."""
    if n_quarters <= 0:
        return Decimal(0)
    r = (annual_rate_pct / Decimal(100)) / Decimal(4)
    if r == 0:
        return money(principal / Decimal(n_quarters))
    factor = (Decimal(1) + r) ** n_quarters
    installment = principal * r * factor / (factor - Decimal(1))
    return money(installment)


def _seasonality_factor(business_category: str | None, month: int) -> Decimal:
    if not business_category:
        return Decimal("1.00")
    with get_cursor() as cur:
        cur.execute(
            "SELECT revenue_factor FROM seasonality WHERE business_category = %s AND month = %s",
            (business_category, month),
        )
        row = cur.fetchone()
    return Decimal(str(row["revenue_factor"])) if row else Decimal("1.00")


@dataclass(frozen=True)
class ScheduleRow:
    installment_number: int
    phase: str  # "moratorium" | "repayment"
    opening_balance: Decimal
    interest_charged: Decimal
    principal_component: Decimal
    installment_amount: Decimal
    seasonality_factor: Decimal
    adjusted_installment_amount: Decimal
    closing_balance: Decimal
    cumulative_interest: Decimal
    cumulative_principal: Decimal


VALID_MORATORIUM_MODES = ("CAPITALISED", "SERVICED", "WAIVED")


def build_amortisation_schedule(
    loan_amount: Decimal,
    annual_rate_pct: Decimal,
    tenure_months: int,
    moratorium_months: int,
    moratorium_mode: str,
    business_category: str | None = None,
    start_month: int = 1,
) -> list[ScheduleRow]:
    if moratorium_mode not in VALID_MORATORIUM_MODES:
        raise ValueError(f"moratorium_mode must be one of {VALID_MORATORIUM_MODES}")

    loan_amount = money(loan_amount)
    annual_rate_pct = Decimal(str(annual_rate_pct))
    r = (annual_rate_pct / Decimal(100)) / Decimal(4)

    total_quarters = tenure_months // 3
    moratorium_quarters = moratorium_months // 3
    repayment_quarters = total_quarters - moratorium_quarters
    if repayment_quarters <= 0:
        raise ValueError(
            f"Moratorium ({moratorium_months}mo) leaves no repayment period within "
            f"tenure ({tenure_months}mo) — check scheme config."
        )

    schedule: list[ScheduleRow] = []
    balance = loan_amount
    cum_interest = Decimal(0)
    cum_principal = Decimal(0)
    month = start_month
    n = 0

    for _ in range(moratorium_quarters):
        n += 1
        interest = money(balance * r)
        if moratorium_mode == "CAPITALISED":
            installment = Decimal(0)
            principal_comp = Decimal(0)
            closing = money(balance + interest)   # accrues onto principal
        elif moratorium_mode == "SERVICED":
            installment = interest                 # paid now, principal untouched
            principal_comp = Decimal(0)
            closing = balance
        else:  # WAIVED
            interest = Decimal(0)
            installment = Decimal(0)
            principal_comp = Decimal(0)
            closing = balance
        cum_interest = money(cum_interest + interest)
        schedule.append(ScheduleRow(
            installment_number=n, phase="moratorium", opening_balance=balance,
            interest_charged=interest, principal_component=principal_comp,
            installment_amount=installment, seasonality_factor=Decimal("1.00"),
            adjusted_installment_amount=installment, closing_balance=closing,
            cumulative_interest=cum_interest, cumulative_principal=cum_principal,
        ))
        balance = closing
        month = ((month - 1 + 3) % 12) + 1

    base_installment = quarterly_payment_amount(balance, annual_rate_pct, repayment_quarters)
    for _ in range(repayment_quarters):
        n += 1
        interest = money(balance * r)
        principal_comp = money(base_installment - interest)
        if principal_comp > balance:
            principal_comp = balance
        installment = money(interest + principal_comp)
        factor = _seasonality_factor(business_category, month)
        adjusted = money(installment * factor)
        closing = money(balance - principal_comp)
        cum_interest = money(cum_interest + interest)
        cum_principal = money(cum_principal + principal_comp)
        schedule.append(ScheduleRow(
            installment_number=n, phase="repayment", opening_balance=balance,
            interest_charged=interest, principal_component=principal_comp,
            installment_amount=installment, seasonality_factor=factor,
            adjusted_installment_amount=adjusted, closing_balance=closing,
            cumulative_interest=cum_interest, cumulative_principal=cum_principal,
        ))
        balance = closing
        month = ((month - 1 + 3) % 12) + 1

    return schedule


# ---------------------------------------------------------------------------
# Interval-aware viability verdict (R2 — scenario counts, not a colour)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ViabilityScenario:
    monthly_revenue: Decimal
    monthly_opex: Decimal
    quarterly_surplus: Decimal
    coverage_ratio: Decimal
    repayable: bool


@dataclass(frozen=True)
class ViabilityResult:
    scenarios: list[ViabilityScenario]
    repayable_count: int
    n_scenarios: int
    verdict: str


def compute_viability(
    monthly_revenue: Evidence,
    monthly_opex: Decimal,
    quarterly_installment: Decimal,
    n_scenarios: int = 10,
    seed: str = "artha_setu",
) -> ViabilityResult:
    """Samples n_scenarios points across the revenue's own [low, high] band
    (already +/-40%, attached by the Feasibility Engine) and an independent
    +/-25% cost band, per reference §4.5. Deterministically seeded so the
    same inputs always produce the same verdict — 'Code computes.'"""
    rng = random.Random(seed)
    monthly_opex = money(monthly_opex)
    opex_low = money(monthly_opex * (Decimal(1) - COST_UNCERTAINTY_PCT))
    opex_high = money(monthly_opex * (Decimal(1) + COST_UNCERTAINTY_PCT))
    rev_low, rev_high = Decimal(str(monthly_revenue.low)), Decimal(str(monthly_revenue.high))

    scenarios: list[ViabilityScenario] = []
    repayable_count = 0
    for _ in range(n_scenarios):
        rev = money(Decimal(str(rng.uniform(float(rev_low), float(rev_high)))))
        opex = money(Decimal(str(rng.uniform(float(opex_low), float(opex_high)))))
        monthly_surplus = money(rev - opex)
        quarterly_surplus = money(monthly_surplus * Decimal(3))
        coverage = (
            money(quarterly_surplus / quarterly_installment) if quarterly_installment > 0 else Decimal(0)
        )
        repayable = coverage >= 1
        if repayable:
            repayable_count += 1
        scenarios.append(ViabilityScenario(
            monthly_revenue=rev, monthly_opex=opex, quarterly_surplus=quarterly_surplus,
            coverage_ratio=coverage, repayable=repayable,
        ))

    return ViabilityResult(
        scenarios=scenarios, repayable_count=repayable_count, n_scenarios=n_scenarios,
        verdict=f"Repayable in {repayable_count} of {n_scenarios} scenarios",
    )
