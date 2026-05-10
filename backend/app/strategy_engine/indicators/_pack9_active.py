"""Pack 9 — 12 bands + envelopes + advanced moving averages.

Discovery-time collisions vs Pack-2-through-8:

    * ``tema``    — already active (Phase 9 era)
      → substituted with ``arnaud_legoux_ma`` (ALMA — Gaussian-
        weighted, distinct mechanism)
    * ``hull_ma`` — already active (Phase 9 era)
      → substituted with ``vidya`` (CMO-adapted EMA — distinct
        from ``kaufman_ama``'s efficiency-ratio adaptation, so
        the registry now offers two genuinely-different adaptive
        MA flavours)

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT — schema has no
ADVANCED tier; spec's "ADVANCED" mapped to EXPERT):

    INTERMEDIATE (6) — envelope_upper, envelope_lower,
                       price_channel_high, price_channel_low,
                       linear_regression_upper,
                       linear_regression_lower
    EXPERT (6)       — starc_upper, starc_lower,
                       arnaud_legoux_ma, vidya, zlema,
                       kaufman_ama

Pine importer rewires:

    * ``ta.highest`` → ``price_channel_high``  (was a stale
      "donchian coming_soon" note — donchian became active in
      an earlier pack; the note never got updated)
    * ``ta.lowest``  → ``price_channel_low``   (same fix)

Net-new Pine entries: none (highest/lowest were already in the
parser's SUPPORTED_TA_INDICATORS set; the mapper branches just
get correct destinations now).
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

# ─── Bands & Envelopes (4) ────────────────────────────────────────────


_ENVELOPE_UPPER = IndicatorMetadata(
    id="envelope_upper",
    name="MA Envelope — Upper",
    category="Volatility",
    description=(
        "Upper band of a fixed-percent SMA envelope. ``upper = "
        "SMA(close, period) * (1 + pct/100)``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="pct", type=InputType.NUMBER, default=2.5, min=0.0, max=50.0),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MA Envelope upper band fixed-percent above SMA. Price "
        "envelope upper touch karne par overbought / reversion "
        "signal."
    ),
    tags=["envelope", "volatility"],
    calculation_function="envelope_upper",
)


_ENVELOPE_LOWER = IndicatorMetadata(
    id="envelope_lower",
    name="MA Envelope — Lower",
    category="Volatility",
    description=(
        "Lower band of a fixed-percent SMA envelope. ``lower = "
        "SMA(close, period) * (1 - pct/100)``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="pct", type=InputType.NUMBER, default=2.5, min=0.0, max=50.0),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MA Envelope lower band fixed-percent below SMA. Price "
        "envelope lower touch = oversold / reversion candidate."
    ),
    tags=["envelope", "volatility"],
    calculation_function="envelope_lower",
)


_STARC_UPPER = IndicatorMetadata(
    id="starc_upper",
    name="STARC Bands — Upper",
    category="Volatility",
    description=(
        "Stoller Average Range Channel upper band — SMA + "
        "atr_mult * ATR. Volatility-aware envelope (Manning Stoller)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=5, min=2, max=200),
        InputSpec(
            name="atr_period", type=InputType.NUMBER, default=15, min=2, max=200,
        ),
        InputSpec(
            name="atr_mult", type=InputType.NUMBER, default=1.5, min=0.1, max=10.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "STARC Bands ATR-based volatility envelope. Bollinger "
        "ka cousin — ATR use karta hai stddev ke jagah, jo "
        "outliers se kam affected hota hai."
    ),
    tags=["envelope", "atr"],
    calculation_function="starc_upper",
)


_STARC_LOWER = IndicatorMetadata(
    id="starc_lower",
    name="STARC Bands — Lower",
    category="Volatility",
    description=(
        "Stoller Average Range Channel lower band. Companion "
        "to STARC upper."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=5, min=2, max=200),
        InputSpec(
            name="atr_period", type=InputType.NUMBER, default=15, min=2, max=200,
        ),
        InputSpec(
            name="atr_mult", type=InputType.NUMBER, default=1.5, min=0.1, max=10.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "STARC Lower band volatility-aware support level. Close "
        "iske niche jaaye to strong move ka signal."
    ),
    tags=["envelope", "atr"],
    calculation_function="starc_lower",
)


# ─── Channels (4) ─────────────────────────────────────────────────────


_PRICE_CHANNEL_HIGH = IndicatorMetadata(
    id="price_channel_high",
    name="Price Channel — High",
    category="Channel",
    description=(
        "Highest high over a rolling ``period`` window — mirror "
        "of Pine ``ta.highest(high, length)``. Distinct from "
        "the existing donchian_channel midline output."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.highest"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Price Channel High = trailing highest-high. Breakout "
        "above = trend continuation signal. Pine ``ta.highest`` "
        "ka direct equivalent."
    ),
    tags=["channel", "breakout"],
    calculation_function="price_channel_high",
)


_PRICE_CHANNEL_LOW = IndicatorMetadata(
    id="price_channel_low",
    name="Price Channel — Low",
    category="Channel",
    description=(
        "Lowest low over a rolling ``period`` window — mirror "
        "of Pine ``ta.lowest(low, length)``."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.lowest"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Price Channel Low = trailing lowest-low. Breakdown "
        "below = trend reversal / continuation in downtrend."
    ),
    tags=["channel", "breakout"],
    calculation_function="price_channel_low",
)


_LINEAR_REGRESSION_UPPER = IndicatorMetadata(
    id="linear_regression_upper",
    name="LinReg Channel — Upper",
    category="Channel",
    description=(
        "Linear-regression line + std_mult * residual stddev. "
        "Tracks price's deviation from the rolling least-"
        "squares best-fit."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(
            name="std_mult", type=InputType.NUMBER, default=2.0, min=0.0, max=10.0,
        ),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "LinReg Channel Upper = linear regression line + 2 sigma. "
        "Price upper boundary touch = overbought relative to trend."
    ),
    tags=["channel", "regression"],
    calculation_function="linear_regression_upper",
)


_LINEAR_REGRESSION_LOWER = IndicatorMetadata(
    id="linear_regression_lower",
    name="LinReg Channel — Lower",
    category="Channel",
    description=(
        "Linear-regression line - std_mult * residual stddev. "
        "Companion to LinReg upper."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(
            name="std_mult", type=InputType.NUMBER, default=2.0, min=0.0, max=10.0,
        ),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "LinReg Channel Lower = regression line - 2 sigma. "
        "Lower boundary touch = oversold relative to trend."
    ),
    tags=["channel", "regression"],
    calculation_function="linear_regression_lower",
)


# ─── Advanced MAs (4) ─────────────────────────────────────────────────


_ARNAUD_LEGOUX_MA = IndicatorMetadata(
    id="arnaud_legoux_ma",
    name="Arnaud Legoux MA (ALMA)",
    category="Trend",
    description=(
        "Gaussian-weighted moving average (Arnaud Legoux & "
        "Dimitrios Kouzis-Loukas, 2009). Faster + smoother than "
        "EMA on responsive price action."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=9, min=2, max=500),
        InputSpec(name="sigma", type=InputType.NUMBER, default=6.0, min=0.5, max=50.0),
        InputSpec(name="offset", type=InputType.NUMBER, default=0.85, min=0.0, max=1.0),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ALMA Gaussian-weighted MA — kernel peak (offset=0.85) "
        "recent bars ko zyada weight deta hai. EMA se smoother + "
        "less laggy."
    ),
    tags=["trend", "ma", "advanced"],
    calculation_function="arnaud_legoux_ma",
)


_VIDYA = IndicatorMetadata(
    id="vidya",
    name="Variable Index Dynamic Average (VIDYA)",
    category="Trend",
    description=(
        "CMO-adapted EMA (Tushar Chande, 1992). Volatility "
        "index from CMO accelerates in trends, slows in chop. "
        "Distinct mechanism vs KAMA's efficiency ratio."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=9, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "VIDYA volatility index ke basis pe smoothing speed "
        "adapt karta hai. Trending market mein fast, chop mein "
        "slow — whipsaw kam."
    ),
    tags=["trend", "ma", "adaptive"],
    calculation_function="vidya",
)


_ZLEMA = IndicatorMetadata(
    id="zlema",
    name="Zero-Lag EMA (ZLEMA)",
    category="Trend",
    description=(
        "EMA over a de-lagged input series (John Ehlers). "
        "Removes intrinsic EMA lag at the cost of sharper "
        "noise response."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ZLEMA Ehlers ka zero-lag variant — EMA ki delay hata "
        "deta hai. Tradeoff: signals tez but choppy market mein "
        "false signals zyada."
    ),
    tags=["trend", "ma", "ehlers"],
    calculation_function="zlema",
)


_KAUFMAN_AMA = IndicatorMetadata(
    id="kaufman_ama",
    name="Kaufman Adaptive MA (KAMA)",
    category="Trend",
    description=(
        "Adapts smoothing speed to the efficiency ratio (Perry "
        "Kaufman, 1995). Trending price → fast smoothing; "
        "choppy price → slow smoothing."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=2, max=200),
        InputSpec(name="fast", type=InputType.NUMBER, default=2, min=1, max=50),
        InputSpec(name="slow", type=InputType.NUMBER, default=30, min=2, max=200),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "KAMA efficiency ratio (direct movement / total path) "
        "se adapt karta hai. Strong trend ke time fast follow "
        "karta hai, sideways mein flat rehta hai."
    ),
    tags=["trend", "ma", "adaptive"],
    calculation_function="kaufman_ama",
)


# ─── Aggregate ─────────────────────────────────────────────────────────


PACK9_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _ENVELOPE_UPPER,
    _ENVELOPE_LOWER,
    _STARC_UPPER,
    _STARC_LOWER,
    _PRICE_CHANNEL_HIGH,
    _PRICE_CHANNEL_LOW,
    _LINEAR_REGRESSION_UPPER,
    _LINEAR_REGRESSION_LOWER,
    _ARNAUD_LEGOUX_MA,
    _VIDYA,
    _ZLEMA,
    _KAUFMAN_AMA,
)


__all__ = ["PACK9_ACTIVE_INDICATORS"]
