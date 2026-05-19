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
)


__all__ = ["PACK_COMPLETION_WAVE2_ACTIVE_INDICATORS"]
