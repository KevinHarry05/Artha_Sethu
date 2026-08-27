"""
The single object that flows out of the pipeline (§4.7 of the project
reference) into the narration layer and the dashboard/PDF renderer.

Stage 1: shape only. Populated once modules 0, 2a, 1, 2b exist.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceStep:
    """One row of the calculation trace (R6): every step is inspectable."""
    step: str
    inputs: dict[str, Any]
    formula: str
    output: Any
    sources: list[str] = field(default_factory=list)


@dataclass
class ReportObject:
    report_id: str
    data_snapshot_version: str
    generated_at: str  # ISO 8601 timestamp

    location: dict[str, Any] = field(default_factory=dict)          # module 0 output
    eligibility: dict[str, Any] = field(default_factory=dict)       # pre-screening gate output
    financial_structuring: dict[str, Any] = field(default_factory=dict)  # module 2a output
    feasibility: dict[str, Any] = field(default_factory=dict)       # module 1 output
    repayment_viability: dict[str, Any] = field(default_factory=dict)    # module 2b output
    dashboard: dict[str, Any] = field(default_factory=dict)          # composite overview, computed from the above

    trace: list[TraceStep] = field(default_factory=list)
