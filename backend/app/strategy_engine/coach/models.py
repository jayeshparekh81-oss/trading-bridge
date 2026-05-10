"""Pydantic models for the Strategy Coach health card.

Both models are frozen so the coach's output can be safely cached or
deep-equality-tested. ``MetricGrade`` is the per-metric row; the
:class:`StrategyHealthCard` aggregates them into a top-level summary.

The ``unit`` field on each :class:`MetricGrade` is the suffix to use
when displaying ``your_value`` (``"%"`` for percentages, ``"x"`` for
ratios, ``""`` for trade counts). The model itself doesn't render —
the UI does.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Per-metric grade — locked vocabulary used everywhere in the coach.
MetricGradeLevel = Literal["EXCELLENT", "GOOD", "ACCEPTABLE", "CONCERNING"]

#: Overall A-F grade — same vocabulary as Phase 4's TrustScore for
#: cross-engine consistency.
OverallGrade = Literal["A", "B", "C", "D", "F"]


class MetricGrade(BaseModel):
    """One row in the health card — a single metric's grade and tip."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str = Field(..., min_length=1, max_length=64)
    your_value: float
    unit: str = Field(default="", max_length=16)
    ideal_excellent: str = Field(..., min_length=1, max_length=64)
    ideal_good: str = Field(..., min_length=1, max_length=64)
    ideal_acceptable: str = Field(..., min_length=1, max_length=64)
    ideal_concerning: str = Field(..., min_length=1, max_length=64)
    your_grade: MetricGradeLevel
    hinglish_tip: str = Field(..., min_length=1, max_length=512)


class StrategyHealthCard(BaseModel):
    """Top-level coach output — aggregate grade + per-metric breakdown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_grade: OverallGrade
    overall_summary_hinglish: str = Field(..., min_length=1, max_length=512)
    metric_grades: tuple[MetricGrade, ...] = Field(default_factory=tuple)
    learning_tips: tuple[str, ...] = Field(default_factory=tuple)
    next_steps_hinglish: tuple[str, ...] = Field(default_factory=tuple)


__all__ = [
    "MetricGrade",
    "MetricGradeLevel",
    "OverallGrade",
    "StrategyHealthCard",
]
