"""Pack 4 — 12 S/R + statistical + volatility/range indicators.

Mix of net-new ids and coming-soon promotions:

    Promotions (coming_soon → active):
        std_dev, camarilla_pivots, woodie_pivots,
        historical_volatility, regression_channel

    Net-new:
        swing_high, swing_low, correlation_coefficient, variance,
        true_range, high_low_spread, inside_bar

The same dict-comp later-wins splat used by Pack 2 lets the
promotion rows override the same-id coming-soon stubs.

All entries marked INTERMEDIATE difficulty — the existing
``test_beginner_recommended_subset`` locks the beginner set to
``{ema, sma, rsi, volume_sma}`` and any BEGINNER addition trips
that lock.

Pine importer: 5 entries map to real ``ta.*`` functions
(``pivothigh / pivotlow / stdev / variance / correlation``); the
other 7 are builder-UI only because Pine has no equivalent
function name (we don't invent recognition for nonexistent calls
— Pack 3 lesson).
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

# ─── Support / Resistance (5) ──────────────────────────────────────────


_CAMARILLA_PIVOTS = IndicatorMetadata(
    id="camarilla_pivots",
    name="Camarilla Pivots",
    category="Support/Resistance",
    description=(
        "Camarilla pivot ladder — R3 / R4 / S3 / S4 levels derived "
        "from the prior bar's H/L/C using the 1.1 / 4 and 1.1 / 2 "
        "scaling. Heavily used in Indian intraday (Slade, 1989)."
    ),
    inputs=[],
    outputs=["r3", "r4", "s3", "s4"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "S3/R3 mean-reversion targets — price often bounces yahan se. "
        "S4/R4 breakout levels — yeh cross karte hi trend confirm "
        "hota hai."
    ),
    tags=["support-resistance", "pivot", "intraday"],
    calculation_function="camarilla_pivots",
)

_WOODIE_PIVOTS = IndicatorMetadata(
    id="woodie_pivots",
    name="Woodie Pivots",
    category="Support/Resistance",
    description=(
        "Woodie pivot variant — central pivot weighted by the prior "
        "close (PP = (H + L + 2C) / 4). Plus R1, R2, S1, S2."
    ),
    inputs=[],
    outputs=["pp", "r1", "r2", "s1", "s2"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Woodie ka PP close-weighted hai — Classic ke compared mein "
        "current price action ko zyada importance deta hai. Day "
        "trading mein useful jab close direction strong hota hai."
    ),
    tags=["support-resistance", "pivot", "intraday"],
    calculation_function="woodie_pivots",
)

_SWING_HIGH = IndicatorMetadata(
    id="swing_high",
    name="Swing High",
    category="Support/Resistance",
    description=(
        "Pivot-high level (matches Pine ``ta.pivothigh``). Bar at "
        "index ``p`` is a swing high iff its high is the maximum "
        "across ``[p - left_bars, p + right_bars]``. Confirmed value "
        "appears ``right_bars`` bars after the actual pivot."
    ),
    inputs=[
        InputSpec(name="left_bars", type=InputType.NUMBER, default=5, min=1, max=200),
        InputSpec(name="right_bars", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["level"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.pivothigh"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Swing High dynamic resistance level — pichli pivot high "
        "ko break karna trend continuation signal hai."
    ),
    tags=["support-resistance", "pivot", "structure"],
    calculation_function="swing_high",
)

_SWING_LOW = IndicatorMetadata(
    id="swing_low",
    name="Swing Low",
    category="Support/Resistance",
    description=(
        "Pivot-low level (matches Pine ``ta.pivotlow``). Mirror of "
        "swing_high — confirmed value appears ``right_bars`` bars "
        "after the pivot."
    ),
    inputs=[
        InputSpec(name="left_bars", type=InputType.NUMBER, default=5, min=1, max=200),
        InputSpec(name="right_bars", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["level"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=["ta.pivotlow"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Swing Low dynamic support level — pichla swing low break "
        "ho jaye to trend reversal warning."
    ),
    tags=["support-resistance", "pivot", "structure"],
    calculation_function="swing_low",
)

_REGRESSION_CHANNEL = IndicatorMetadata(
    id="regression_channel",
    name="Regression Channel",
    category="Support/Resistance",
    description=(
        "Linear regression channel — best-fit line through the last "
        "``period`` bars plus ±``std_dev`` standard deviations of the "
        "residuals. Outputs middle / upper / lower."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(
            name="std_dev", type=InputType.NUMBER, default=2.0, min=0.1, max=10
        ),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["middle", "upper", "lower"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Regression Channel se trend ka direction + dynamic S/R "
        "milta hai. Price upper band tag karte hi mean-reversion "
        "trade ka chance, lower band se bounce buy ka."
    ),
    tags=["support-resistance", "regression", "channels"],
    calculation_function="regression_channel",
)

# ─── Statistical (4) ───────────────────────────────────────────────────


_STD_DEV = IndicatorMetadata(
    id="std_dev",
    name="Standard Deviation",
    category="Statistical",
    description=(
        "Population standard deviation (matches Pine ``ta.stdev``) — "
        "n-denominator variance, square-rooted. Volatility primitive "
        "underlying Bollinger Bands."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.stdev"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Standard Deviation rolling volatility measure hai — high "
        "values mein wide stops chahiye, low values mein consolidation "
        "ki sambhavna."
    ),
    tags=["statistical", "volatility"],
    calculation_function="std_dev",
)

_VARIANCE = IndicatorMetadata(
    id="variance",
    name="Variance",
    category="Statistical",
    description=(
        "Population variance (matches Pine ``ta.variance`` with the "
        "default biased=true). Square of Standard Deviation."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.variance"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Variance volatility ka unsquared form hai — kuch quant "
        "models (e.g. Sharpe, Markowitz) mein direct use hota hai."
    ),
    tags=["statistical", "volatility"],
    calculation_function="variance",
)

_CORRELATION_COEFFICIENT = IndicatorMetadata(
    id="correlation_coefficient",
    name="Correlation Coefficient",
    category="Statistical",
    description=(
        "Pearson correlation between two price sources over a "
        "rolling window (matches Pine ``ta.correlation``). Range "
        "[-1, +1]."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(name="source_a", type=InputType.SOURCE, default="close"),
        InputSpec(name="source_b", type=InputType.SOURCE, default="open"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.correlation"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Correlation rolling relationship dikhata hai — close vs "
        "open ka high correlation matlab same-direction bars, kam "
        "matlab choppy / reversal-prone tape."
    ),
    tags=["statistical", "correlation"],
    calculation_function="correlation_coefficient",
)

_HISTORICAL_VOLATILITY = IndicatorMetadata(
    id="historical_volatility",
    name="Historical Volatility",
    category="Statistical",
    description=(
        "Annualised stddev of log returns, expressed as a percent. "
        "Default ``annualization=252`` matches the trading-day count "
        "for daily Indian / US equity data."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(
            name="annualization", type=InputType.NUMBER, default=252, min=1, max=10000
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Historical Volatility annualised hai — direct comparable "
        "across symbols. Options pricing, position sizing aur regime "
        "filtering ke liye useful."
    ),
    tags=["statistical", "volatility"],
    calculation_function="historical_volatility",
)

# ─── Volatility / Range (3) ────────────────────────────────────────────


_TRUE_RANGE = IndicatorMetadata(
    id="true_range",
    name="True Range",
    category="Volatility",
    description=(
        "Single-bar True Range (Wilder, 1978) — unsmoothed input to "
        "ATR. ``max(high-low, |high-prev_close|, |low-prev_close|)``. "
        "Bar 0 is just ``high - low``."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "True Range raw volatility tick hai — single-bar stops, "
        "low-range bars filter, ya volatility-aware sizing ke liye "
        "use karo."
    ),
    tags=["volatility", "range"],
    calculation_function="true_range",
)

_HIGH_LOW_SPREAD = IndicatorMetadata(
    id="high_low_spread",
    name="High-Low Spread %",
    category="Volatility",
    description=(
        "Bar range as a percent of close: ``(high - low) / close * "
        "100``. Unitless across different-priced symbols."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "HL Spread % se filter karo — bohot kam values matlab "
        "consolidation / no-trade, bohot high values matlab event "
        "candle (gap up/down)."
    ),
    tags=["volatility", "range"],
    calculation_function="high_low_spread",
)

_INSIDE_BAR = IndicatorMetadata(
    id="inside_bar",
    name="Inside Bar",
    category="Pattern",
    description=(
        "Inside Bar — single-bar consolidation pattern. Bar i is "
        "inside iff ``high[i] <= high[i-1]`` and ``low[i] >= "
        "low[i-1]``. Returns 1.0 / 0.0; bar 0 is None."
    ),
    inputs=[],
    outputs=["signal"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Inside Bar consolidation signal hai — break of inside-bar "
        "range often trend continuation marks. NR4/NR7 setups mein "
        "common building block."
    ),
    tags=["pattern", "consolidation", "single-bar"],
    calculation_function="inside_bar",
)

# ─── Aggregate ─────────────────────────────────────────────────────────


PACK4_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _CAMARILLA_PIVOTS,
    _WOODIE_PIVOTS,
    _SWING_HIGH,
    _SWING_LOW,
    _REGRESSION_CHANNEL,
    _STD_DEV,
    _VARIANCE,
    _CORRELATION_COEFFICIENT,
    _HISTORICAL_VOLATILITY,
    _TRUE_RANGE,
    _HIGH_LOW_SPREAD,
    _INSIDE_BAR,
)


__all__ = ["PACK4_ACTIVE_INDICATORS"]
