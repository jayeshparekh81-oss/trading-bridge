"""Strategy Coach — Hinglish health-card education layer.

Reads Phase 3 ``BacktestResult`` (and optionally Phase 4
``ReliabilityReport``) and emits a beginner-friendly health card with:

    * 7 metric grades (excellent / good / acceptable / concerning) with
      locked benchmark thresholds.
    * Per-metric Hinglish tip explaining the user's value vs the ideal
      range. ASCII-safe text plus ``₹`` and ``%``.
    * An overall A-F grade derived from the metric average.
    * Next-step suggestions tailored to the overall grade band.

Pure deterministic — no LLM, no network, no clock reads. The same
``BacktestResult`` always produces the same :class:`StrategyHealthCard`.
``test_no_llm_or_network_imports`` AST-walks this package to keep that
guarantee load-bearing.
"""

from __future__ import annotations

from app.strategy_engine.coach.generator import generate_health_card
from app.strategy_engine.coach.models import (
    MetricGrade,
    MetricGradeLevel,
    OverallGrade,
    StrategyHealthCard,
)

__all__ = [
    "MetricGrade",
    "MetricGradeLevel",
    "OverallGrade",
    "StrategyHealthCard",
    "generate_health_card",
]
