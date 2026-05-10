"""Aggregation logic — average score + worst-case status across metrics.

The deviation_score is a 0-100 average over the per-metric severity
scores (see :data:`SEVERITY_SCORE`). The overall ``status`` is the
*worst* severity any single metric reached — a single critical metric
escalates the whole report regardless of how many normal metrics
counterbalance it (the spec is explicit: "Final status = max severity
across all metrics").
"""

from __future__ import annotations

from app.strategy_engine.deviation.constants import (
    SEVERITY_RANK,
    SEVERITY_SCORE,
)
from app.strategy_engine.deviation.models import DeviationMetric, Severity


def aggregate_score(
    metrics: list[DeviationMetric],
) -> tuple[float, Severity]:
    """Return ``(deviation_score, status)`` for ``metrics``.

    Empty input collapses to ``(0.0, "normal")`` — when no metrics
    could run (because the actual stats lacked the inputs), there is
    no deviation to report.
    """
    if not metrics:
        return 0.0, "normal"

    score = sum(SEVERITY_SCORE[m.severity] for m in metrics) / len(metrics)
    worst: Severity = max(
        (m.severity for m in metrics),
        key=lambda s: SEVERITY_RANK[s],
    )
    return score, worst


def decision_flags(status: Severity) -> tuple[bool, bool, bool]:
    """Map ``status`` to ``(should_pause, should_reduce_size, should_switch_to_paper)``.

    Mirrors the locked rule from the spec:

        * ``critical`` — pause + paper + reduce
        * ``warning``  — paper + reduce (no pause yet)
        * ``watch``    — all False (signal is in the status itself)
        * ``normal``   — all False
    """
    if status == "critical":
        return True, True, True
    if status == "warning":
        return False, True, True
    return False, False, False


__all__ = ["aggregate_score", "decision_flags"]
