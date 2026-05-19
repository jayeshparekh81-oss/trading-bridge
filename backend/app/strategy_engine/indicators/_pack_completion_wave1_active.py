"""Indicator-completion Wave 1 pack — new implementations to close the
gap between ``frontend/src/lib/indicators/content/`` and the backend
compute registry.

Strictly additive: every entry here is a NEW indicator id; no existing
IndicatorMetadata is touched. New calculation files live in
``calculations/`` per the existing convention.

Audit reference: /tmp/INDICATOR_GAP_AUDIT_2026-05-19.md
"""

from __future__ import annotations

from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
    InputSpec,
    InputType,
)


_STANDARD_DEVIATION = IndicatorMetadata(
    id="standard_deviation",
    name="Standard Deviation",
    category="Volatility",
    description=(
        "Rolling population standard deviation of the source over "
        "``period`` bars. Matches Pine ``ta.stdev`` (population, not "
        "sample). Foundational primitive — feeds Bollinger Bands, "
        "Z-score, and channel-band indicators."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=1, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.stdev"],
    difficulty=IndicatorDifficulty.BEGINNER,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Standard deviation measure karta values apni mean se kitna "
        "spread out hain. Volatility ka basic measure — high stdev = "
        "high volatility, low stdev = calm/range-bound market."
    ),
    tags=["volatility", "statistics", "library-canonical"],
    calculation_function="standard_deviation",
)


PACK_COMPLETION_WAVE1_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _STANDARD_DEVIATION,
)


__all__ = ["PACK_COMPLETION_WAVE1_ACTIVE_INDICATORS"]
