"""Indicator-completion Wave 2 + 3 pack — medium/high-complexity
implementations from the locked variants in
``/tmp/INDICATOR_REFERENCES_2026-05-19.md``.

Strictly additive — every entry is a NEW indicator id; no existing
IndicatorMetadata is modified.

Wave 2: swing_index, schaff_trend_cycle, supports_resistances
Wave 3: accumulative_swing_index, volume_profile, gaussian_channel
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


_SCHAFF_TREND_CYCLE = IndicatorMetadata(
    id="schaff_trend_cycle",
    name="Schaff Trend Cycle (STC)",
    category="Momentum",
    description=(
        "Doug Schaff's cycle-aware MACD variant. Two stochastic + "
        "smoothing passes over the MACD line produce a fast-moving "
        "0..100 oscillator. Pine ``ta.stc(close, 10, 23, 50)`` parity. "
        "Defaults: fast=23, slow=50, cycle=10, factor=0.5."
    ),
    inputs=[
        InputSpec(name="fast_length", type=InputType.NUMBER, default=23, min=2, max=500),
        InputSpec(name="slow_length", type=InputType.NUMBER, default=50, min=2, max=500),
        InputSpec(name="cycle_length", type=InputType.NUMBER, default=10, min=2, max=200),
        InputSpec(name="factor", type=InputType.NUMBER, default=0.5, min=0.01, max=1.0),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.stc"],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "STC MACD ka faster + smoother version — early trend-change "
        "detection. 0..100 bounded; 25 ke neeche oversold-trending, "
        "75 ke upar overbought-trending. Cross + slope-flip combination "
        "se entry/exit time karte."
    ),
    tags=["momentum", "stc", "library-canonical"],
    calculation_function="schaff_trend_cycle",
)


_SWING_INDEX = IndicatorMetadata(
    id="swing_index",
    name="Swing Index (SI)",
    category="Momentum",
    description=(
        "Welles Wilder's Swing Index (1978) — per-bar signed momentum "
        "measure combining today's OHLC with prior bar's OC. 3-branch "
        "R formula based on which True Range component dominates. "
        "limit_move T = 1.0 (LOCKED for equities/indices). Foundation "
        "for the Accumulative Swing Index."
    ),
    inputs=[
        InputSpec(name="limit_move", type=InputType.NUMBER, default=1.0, min=0.01, max=1000.0),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "SI Wilder ka tricky multi-branch formula hai — sign price "
        "direction batata, magnitude price-action strength. Single-bar "
        "value rough hota; aksar ASI mein cumulate karke trade hota."
    ),
    tags=["momentum", "wilder", "library-canonical"],
    calculation_function="swing_index",
)


PACK_COMPLETION_WAVE2_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _SWING_INDEX,
    _SCHAFF_TREND_CYCLE,
)


__all__ = ["PACK_COMPLETION_WAVE2_ACTIVE_INDICATORS"]
