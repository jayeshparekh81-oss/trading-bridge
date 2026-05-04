"""Strategy reliability / trust-score engine.

Phase 4 of the AI trading system. Deterministic, **AI-free** scoring on
top of the Phase 3 ``BacktestResult``. The engine consumes a backtest
output and (optionally) orchestrates further Phase 3 runs for
out-of-sample, walk-forward, and parameter-sensitivity analysis. The
final :class:`ReliabilityReport` is what the UI builder (Phase 5) and
AI advisor (Phase 6) consume to nudge users toward robust strategies.

Public boundary::

    TrustScore / Grade / calculate_trust_score / grade_for
    OOSResult / run_out_of_sample
    WalkForwardResult / WalkForwardWindow / WalkForwardSummary / run_walk_forward
    SensitivityResult / VariantOutcome / run_sensitivity
    ReliabilityReport / build_reliability_report
"""

from __future__ import annotations

from app.strategy_engine.reliability.constants import Grade
from app.strategy_engine.reliability.out_of_sample import (
    OOSResult,
    run_out_of_sample,
)
from app.strategy_engine.reliability.parameter_sensitivity import (
    SensitivityResult,
    VariantOutcome,
    run_sensitivity,
)
from app.strategy_engine.reliability.reliability_report import (
    ReliabilityReport,
    build_reliability_report,
)
from app.strategy_engine.reliability.trust_score import (
    TrustScore,
    calculate_trust_score,
    grade_for,
)
from app.strategy_engine.reliability.walk_forward import (
    WalkForwardResult,
    WalkForwardSummary,
    WalkForwardWindow,
    run_walk_forward,
)

__all__ = [
    "Grade",
    "OOSResult",
    "ReliabilityReport",
    "SensitivityResult",
    "TrustScore",
    "VariantOutcome",
    "WalkForwardResult",
    "WalkForwardSummary",
    "WalkForwardWindow",
    "build_reliability_report",
    "calculate_trust_score",
    "grade_for",
    "run_out_of_sample",
    "run_sensitivity",
    "run_walk_forward",
]
