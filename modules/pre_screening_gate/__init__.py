"""
PRE-SCREENING GATE

Eligibility != routing (project reference §2.5 item 6). Project cost only
determines the scheme *tier*; whether the applicant may use the scheme at
all is decided here, before any financial structuring happens:
  - community matches the scheme's target group
  - annual family income is below the ceiling
  - applicant is not a loan defaulter

Parameters are read from config/scheme_config.yaml — never hardcoded here,
so swapping in a sibling corporation (NBCFDC, NSKFDC, NHFDC) is a config
change, not a code change.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "scheme_config.yaml"


@dataclass(frozen=True)
class EligibilityResult:
    passed: bool
    reasons: list[str]  # empty if passed; one entry per failed check otherwise


def _load_eligibility_config(corporation: str = "nsfdc") -> dict:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return config[corporation]["eligibility"]


def check_eligibility(
    community: str,
    annual_family_income_inr: float,
    is_defaulter: bool,
    corporation: str = "nsfdc",
) -> EligibilityResult:
    """Runs the three-part eligibility gate. All three must pass."""
    rules = _load_eligibility_config(corporation)
    reasons = []

    if community.strip().upper() != rules["community"].strip().upper():
        reasons.append(
            f"Community '{community}' does not match the target group "
            f"for this scheme ('{rules['community']}')."
        )

    income_ceiling = rules["max_annual_family_income"]
    if annual_family_income_inr >= income_ceiling:
        reasons.append(
            f"Annual family income (Rs.{annual_family_income_inr:,.0f}) is at or above "
            f"the ceiling of Rs.{income_ceiling:,.0f}."
        )

    if rules["requires_non_defaulter"] and is_defaulter:
        reasons.append("Applicant has an existing default on record.")

    return EligibilityResult(passed=(len(reasons) == 0), reasons=reasons)
