"""
Shared data contract for every number the system produces.

Rule: no engine emits a bare float. Every value that reaches the Report
Object — or the LLM narration layer — travels as an Evidence, carrying its
own uncertainty range, source and vintage. This is what makes "Roughly
8-14 competing units (Economic Census 2013)" possible instead of "11".

Stage 1: contract only, no producers yet (those arrive with each module).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    value: float
    low: float           # never a bare point estimate
    high: float
    source: str           # e.g. "Economic Census 2013 (via SHRUG v2.1)"
    vintage: str           # e.g. "2013"
    method: str            # e.g. "block-level establishment count, NIC 4-digit"

    def __post_init__(self) -> None:
        if not (self.low <= self.value <= self.high):
            raise ValueError(
                f"Evidence.value ({self.value}) must lie within "
                f"[low={self.low}, high={self.high}]"
            )
