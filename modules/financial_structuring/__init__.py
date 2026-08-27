"""
[2a] FINANCIAL STRUCTURING — pure, deterministic (R4: no AI, no I/O beyond
reading config/activity_templates; fully unit-testable offline).

Implements the real NSFDC scheme (config/scheme_config.yaml), not the
dataset's fictional "SUVIDHA" preset — see docs/DATA_DECISIONS.md.

Three pieces, matching project reference §4.3:
  1. Scheme router      — bands a project cost into a tier, clamps the 90%
                           loan share to the absolute cap (caps override the
                           percentage — reference §2.5 item 3), applies the
                           plantation/construction moratorium exception.
  2. Two-way solver      — Mode A (PS's stated formula: max eligible project
                           cost from margin) and Mode B (margin required for
                           a stated project need) — reference §2.5 item 2.
                           Both are reported alongside the cap-aware routed
                           figures, since the naive formulas can overstate
                           what's actually affordable once caps bind.
  3. Project cost builder — project_cost = capex + working_capital, read
                           from activity_templates (NABARD-sourced, loaded
                           by db/ingest_raw_data.py).

Money is always Decimal, never float (R4).
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

from db.connection import get_cursor

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "scheme_config.yaml"
TWO_DP = Decimal("0.01")


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def _load_config(corporation: str = "nsfdc") -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)[corporation]


def _tiers(config: dict) -> list[tuple[str, dict]]:
    """Scheme tiers ordered by ascending project_cost_max."""
    schemes = config["schemes"]
    return sorted(schemes.items(), key=lambda kv: kv[1]["project_cost_max"])


class OutOfSchemeError(Exception):
    """Project cost exceeds every tier's band — the scheme ends, per
    reference §2.5 item 3. Callers must say so, never extrapolate a tier."""


@dataclass(frozen=True)
class SchemeRoute:
    scheme_key: str
    project_cost: Decimal
    raw_loan_share: Decimal          # 0.90 x project_cost, before clamping
    loan_amount: Decimal              # after clamping to the absolute cap
    margin_required: Decimal           # project_cost - loan_amount
    effective_loan_share_pct: Decimal   # loan_amount / project_cost x 100
    cap_bound: bool                      # True if the absolute cap, not the %, decided the loan
    interest_rate_pct: Decimal
    tenure_months: int
    moratorium_months: int


def route_scheme(project_cost: Decimal, activity: str = "", corporation: str = "nsfdc") -> SchemeRoute:
    """Bands project_cost into a tier and clamps the loan to the cap."""
    project_cost = money(project_cost)
    config = _load_config(corporation)

    matched = None
    for key, tier in _tiers(config):
        if Decimal(str(tier["project_cost_min"])) <= project_cost <= Decimal(str(tier["project_cost_max"])):
            matched = (key, tier)
            break
    if matched is None:
        raise OutOfSchemeError(
            f"Project cost Rs.{project_cost:,.2f} exceeds every scheme tier's band "
            f"(max {config['schemes'][_tiers(config)[-1][0]]['project_cost_max']:,}). "
            "The scheme ends here — do not extrapolate a further tier."
        )

    key, tier = matched
    loan_share_pct = Decimal(str(tier["loan_share_pct"]))
    loan_cap = Decimal(str(tier["loan_cap"]))

    raw_loan = money(project_cost * loan_share_pct)
    loan_amount = min(raw_loan, loan_cap)
    cap_bound = loan_amount < raw_loan
    margin_required = money(project_cost - loan_amount)
    effective_pct = money((loan_amount / project_cost) * Decimal(100)) if project_cost > 0 else Decimal(0)

    moratorium_months = tier["moratorium_months"]
    exception_activities = tier.get("moratorium_exception_activities") or []
    if activity and activity.lower() in [a.lower() for a in exception_activities]:
        moratorium_months = tier["moratorium_exception_months"]

    return SchemeRoute(
        scheme_key=key,
        project_cost=project_cost,
        raw_loan_share=raw_loan,
        loan_amount=loan_amount,
        margin_required=margin_required,
        effective_loan_share_pct=effective_pct,
        cap_bound=cap_bound,
        interest_rate_pct=Decimal(str(tier["beneficiary_interest_pct"])),
        tenure_months=tier["tenure_months"],
        moratorium_months=moratorium_months,
    )


def get_project_cost_components(business_category: str) -> dict:
    """capex + working_capital for a category, from activity_templates."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT cost_component_type, SUM(total_cost_inr) AS total "
            "FROM activity_templates WHERE business_category = %s "
            "GROUP BY cost_component_type",
            (business_category,),
        )
        rows = {r["cost_component_type"]: money(r["total"]) for r in cur.fetchall()}
    if not rows:
        raise ValueError(f"No activity template found for category '{business_category}'")
    capex = rows.get("capex", Decimal(0))
    working_capital = rows.get("opex", Decimal(0))
    return {
        "capex": capex,
        "working_capital": working_capital,
        "operational_project_cost": money(capex + working_capital),
    }


@dataclass(frozen=True)
class MaxEligibilityResult:
    margin_available: Decimal
    naive_max_project_cost: Decimal    # PS's stated formula: margin / 0.10, uncapped
    affordable_max_project_cost: Decimal  # largest project cost this margin actually covers, cap-aware
    route: SchemeRoute | None            # route at affordable_max_project_cost (None if margin is 0)
    note: str


def solve_max_project_cost(margin_available: Decimal, activity: str = "", corporation: str = "nsfdc") -> MaxEligibilityResult:
    """Mode A — PS's stated formula (§4.3), reported alongside the cap-aware
    affordable figure. The naive formula ignores the absolute loan cap and
    can overstate what's actually financeable — see reference §2.5 item 2:
    telling someone with Rs.1L they qualify for Rs.9L of debt manufactures
    the exact failure the PS complains about."""
    margin_available = money(margin_available)
    config = _load_config(corporation)
    naive_max = money(margin_available / Decimal("0.10"))

    if margin_available <= 0:
        return MaxEligibilityResult(
            margin_available=margin_available, naive_max_project_cost=Decimal(0),
            affordable_max_project_cost=Decimal(0), route=None,
            note="No margin capital available.",
        )

    # margin_required(x) is piecewise-linear and monotonic non-decreasing
    # within each tier (slope 1-pct below the cap-break point, slope 1 above
    # it), but can jump *down* across a tier boundary (a cheaper loan-share
    # structure in the next tier). So: invert in closed form within each
    # tier, then take the largest project cost across all tiers whose
    # margin requirement this margin actually covers.
    best_x: Decimal | None = None
    for key, tier in _tiers(config):
        tier_min = Decimal(str(tier["project_cost_min"]))
        tier_max = Decimal(str(tier["project_cost_max"]))
        pct = Decimal(str(tier["loan_share_pct"]))
        cap = Decimal(str(tier["loan_cap"]))
        x_break = money(cap / pct) if pct > 0 else tier_max          # cap starts binding here
        x_break = min(x_break, tier_max)
        margin_at_break = money(x_break * (Decimal(1) - pct))

        if margin_available <= margin_at_break:
            # Uncapped regime: margin = x * (1 - pct)
            x = money(margin_available / (Decimal(1) - pct))
            x = max(tier_min, min(x, x_break))
        else:
            # Capped regime: margin = x - cap
            x = money(margin_available + cap)
            x = max(x_break, min(x, tier_max))

        if tier_min <= x <= tier_max:
            route = route_scheme(x, activity=activity, corporation=corporation)
            if route.margin_required <= margin_available and (best_x is None or x > best_x):
                best_x = x

    affordable_max = best_x if best_x is not None else Decimal(0)
    best_route = route_scheme(affordable_max, activity=activity, corporation=corporation) if affordable_max > 0 else None
    note = "Naive formula matches the cap-aware affordable figure."
    if naive_max != affordable_max:
        note = (
            f"PS's stated formula (margin / 10%) suggests Rs.{naive_max:,.2f}, but the "
            f"scheme's absolute loan cap means only Rs.{affordable_max:,.2f} is actually "
            "financeable with this margin. Reporting the affordable figure — "
            "'borrow right, not borrow max'."
        )

    return MaxEligibilityResult(
        margin_available=margin_available, naive_max_project_cost=naive_max,
        affordable_max_project_cost=affordable_max, route=best_route, note=note,
    )


@dataclass(frozen=True)
class RequiredMarginResult:
    stated_project_need: Decimal
    naive_required_margin: Decimal   # PS's Challenge-section formula: 10% x need, uncapped
    route: SchemeRoute                 # cap-aware route at the stated need
    shortfall: Decimal | None            # margin_required - margin_available, if margin_available given


def solve_required_margin(
    stated_project_need: Decimal,
    activity: str = "",
    margin_available: Decimal | None = None,
    corporation: str = "nsfdc",
) -> RequiredMarginResult:
    """Mode B — the reverse calculation the Challenge section actually asks
    for (§2.5 item 2), which the PS's Expected Solution section omits."""
    stated_project_need = money(stated_project_need)
    naive_margin = money(stated_project_need * Decimal("0.10"))
    route = route_scheme(stated_project_need, activity=activity, corporation=corporation)

    shortfall = None
    if margin_available is not None:
        shortfall = money(route.margin_required - money(margin_available))
        if shortfall < 0:
            shortfall = Decimal(0)

    return RequiredMarginResult(
        stated_project_need=stated_project_need, naive_required_margin=naive_margin,
        route=route, shortfall=shortfall,
    )
