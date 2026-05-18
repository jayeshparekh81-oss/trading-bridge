"""Batch-1 indicator commission — promote 5 coming-soon ids to ACTIVE.

Imported by :mod:`registry` and splatted AFTER ``PHASE9_COMING_SOON_INDICATORS``
so the dict-comprehension keeps the active rows (later splats override
same-id stubs).

Promotes:
    * ``heikin_ashi``         — calculations/heikin_ashi.py
    * ``alma``                — alias to existing arnaud_legoux_ma
    * ``kama``                — calculations/kama.py
    * ``pivot_swing``         — calculations/pivot_swing.py (NEW id)
    * ``fibonacci_retracement`` — calculations/fibonacci_retracement.py (NEW id)

The first three OVERRIDE same-id coming-soon stubs from
``_phase9_coming_soon.py``. The last two are net-new ids.
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


_HEIKIN_ASHI = IndicatorMetadata(
    id="heikin_ashi",
    name="Heikin Ashi",
    category="Pattern",
    description=(
        "Heikin-Ashi candle transform. Each input OHLC bar is averaged "
        "with the prior HA candle to produce a smoothed bar that "
        "highlights trend direction at the cost of obscuring the true "
        "open/close."
    ),
    inputs=[],
    outputs=["ha_open", "ha_high", "ha_low", "ha_close"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.BEGINNER,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "HA candles run clean colour streaks during strong trends; "
        "useful as a binary trend-direction filter. Don't use the HA "
        "OHLC values for entries — they're synthetic."
    ),
    tags=["pattern", "smoothed", "beginner"],
    calculation_function="heikin_ashi",
)


_ALMA = IndicatorMetadata(
    id="alma",
    name="ALMA",
    category="Trend",
    description=(
        "Arnaud Legoux Moving Average — Gaussian-weighted smoothing "
        "with adjustable phase (offset) and sigma. Smoother than EMA "
        "at the same period."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=9, min=2, max=500),
        InputSpec(name="sigma", type=InputType.NUMBER, default=6.0, min=0.5, max=50.0),
        InputSpec(name="offset", type=InputType.NUMBER, default=0.85, min=0.0, max=1.0),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.alma"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ALMA gives a smoother line than EMA at the same period; tune "
        "offset and sigma to taste. Re-exports the calculation already "
        "shipping under id=arnaud_legoux_ma."
    ),
    tags=["trend", "moving-average"],
    calculation_function="alma",
)


_KAMA = IndicatorMetadata(
    id="kama",
    name="KAMA",
    category="Trend",
    description=(
        "Kaufman's Adaptive Moving Average — variable smoothing driven "
        "by an efficiency ratio so the line accelerates in trend and "
        "flattens in chop. Reference: ta.kama in pandas-ta + KAMA in "
        "TA-Lib."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=2, max=200),
        InputSpec(name="fast", type=InputType.NUMBER, default=2, min=1, max=100),
        InputSpec(name="slow", type=InputType.NUMBER, default=30, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.kama"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "KAMA reduces whipsaws in sideways markets while still tracking "
        "strong trends. Cross of price vs KAMA is the canonical entry."
    ),
    tags=["trend", "adaptive", "moving-average"],
    calculation_function="kama",
)


_PIVOT_SWING = IndicatorMetadata(
    id="pivot_swing",
    name="Pivot Swing",
    category="Support/Resistance",
    description=(
        "Signed swing-pivot indicator. Emits +price at a confirmed "
        "swing high, -price at a confirmed swing low, None otherwise. "
        "Wraps swing_high + swing_low into a single binary signal "
        "for the Pivot Reversal strategy port."
    ),
    inputs=[
        InputSpec(name="left_bars", type=InputType.NUMBER, default=5, min=1, max=200),
        InputSpec(name="right_bars", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["signed_level"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Use pivot_swing > 0 to detect a confirmed swing high "
        "(possible short entry / long exit), pivot_swing < 0 for "
        "a confirmed swing low (possible long entry / short exit)."
    ),
    tags=["support-resistance", "pivot", "structure"],
    calculation_function="pivot_swing",
)


_FIBONACCI_RETRACEMENT = IndicatorMetadata(
    id="fibonacci_retracement",
    name="Fibonacci Retracement",
    category="Support/Resistance",
    description=(
        "Fibonacci retracement levels (23.6%, 38.2%, 50%, 61.8%, "
        "78.6%) from the swing high/low in a trailing lookback "
        "window. Bullish mode retraces from swing_high → swing_low; "
        "bearish mode retraces from swing_low → swing_high."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=50, min=2, max=500),
        InputSpec(
            name="direction",
            type=InputType.STRING,
            default="bull",
            description="'bull' or 'bear'",
        ),
    ],
    outputs=[
        "swing_high",
        "swing_low",
        "23.6",
        "38.2",
        "50.0",
        "61.8",
        "78.6",
    ],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Retail traders use the 38.2-61.8% band as the 'buy the dip' "
        "zone in a bullish trend (or 'sell the bounce' in bearish)."
    ),
    tags=["support-resistance", "fibonacci"],
    calculation_function="fibonacci_retracement",
)


BATCH1_COMMISSION_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _HEIKIN_ASHI,
    _ALMA,
    _KAMA,
    _PIVOT_SWING,
    _FIBONACCI_RETRACEMENT,
)


__all__ = ["BATCH1_COMMISSION_ACTIVE_INDICATORS"]
