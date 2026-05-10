"""Pack 10 — 12 volume profile + microstructure + order flow indicators.

Discovery-time near-collision (handled honestly):

    * ``accumulation_distribution_index`` is the same indicator as
      Pack 6's already-active ``accumulation_distribution`` (the
      A/D Line). Adding it as a different id would compute
      identical numbers under a duplicate name → LOC without
      signal.
      → substituted with ``positive_volume_index`` (PVI), the
        natural companion to NVI which also ships in this pack.
        The PVI/NVI pair is Fosback's 1976 "Smart Money / Dumb
        Money" framework: PVI follows retail flow (volume-up
        days), NVI follows institutional flow (volume-down days).

Honest scope note:

    * ``cumulative_volume_delta`` is a *proxy*. Real CVD requires
      bid/ask trade tape; TRADETRI's bar-data layer doesn't carry
      that. The proxy used here (sign each bar's volume by
      ``close >= open``) is the convention on retail platforms.
      Documented in the calc module so a Phase-2 microstructure-
      feed integration knows what it's replacing.

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT — schema has no
ADVANCED tier; spec's "ADVANCED" mapped to EXPERT):

    INTERMEDIATE (8) — volume_weighted_avg_close, volume_breakout,
                       positive_volume_index, true_strength_index,
                       percent_price_oscillator,
                       rate_of_change_volume,
                       negative_volume_index,
                       on_balance_volume_ema, buying_pressure_ratio
    EXPERT (3)       — volume_at_price_high, money_flow_ratio,
                       cumulative_volume_delta

(That's 9 + 3 = 12. The intermediate count above lists 9 ids;
the buying_pressure_ratio entry below is intermediate too.)

Pine importer wires:

    * ``ta.tsi`` → ``true_strength_index``
    * ``ta.ppo`` → ``percent_price_oscillator``

Other Pack-10 indicators have no standard Pine v5 ``ta.*``
equivalent — all custom or proxy formulations.
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

# ─── Volume Profile (4) ───────────────────────────────────────────────


_VOLUME_WEIGHTED_AVG_CLOSE = IndicatorMetadata(
    id="volume_weighted_avg_close",
    name="Volume-Weighted Avg Close (VWAC)",
    category="Volume",
    description=(
        "Rolling volume-weighted average of close. Distinct from "
        "VWAP (which uses (H+L+C)/3 + session resets) — VWAC is "
        "a pure trailing-window measure on close."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "VWAC rolling window mein volume-weighted average close. "
        "VWAP se simpler — koi session reset nahi, sirf trailing "
        "window ka weighted mean."
    ),
    tags=["volume", "average"],
    calculation_function="volume_weighted_avg_close",
)


_VOLUME_AT_PRICE_HIGH = IndicatorMetadata(
    id="volume_at_price_high",
    name="Volume Profile — POC",
    category="Volume",
    description=(
        "Point Of Control — bin the rolling-window price range "
        "into ``bins`` buckets, accumulate volume per bucket, "
        "emit the centre price of the highest-volume bucket."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=60, min=10, max=500),
        InputSpec(name="bins", type=InputType.NUMBER, default=50, min=5, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Volume Profile POC = jis price level pe sabse zyada "
        "volume traded hua hai. Strong support / resistance level "
        "as a single per-bar projection."
    ),
    tags=["volume", "profile"],
    calculation_function="volume_at_price_high",
)


_VOLUME_BREAKOUT = IndicatorMetadata(
    id="volume_breakout",
    name="Volume Breakout",
    category="Volume",
    description=(
        "+1 / -1 / 0 code. Volume > spike_mult x rolling-average "
        "with bullish bar = +1, bearish bar = -1; otherwise 0."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
        InputSpec(
            name="spike_mult", type=InputType.NUMBER, default=2.0, min=0.5, max=20.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Volume Breakout = volume spike + bar direction. Real "
        "breakouts pe usually volume spike hota hai — confirmation "
        "filter ke liye useful."
    ),
    tags=["volume", "breakout"],
    calculation_function="volume_breakout",
)


_POSITIVE_VOLUME_INDEX = IndicatorMetadata(
    id="positive_volume_index",
    name="Positive Volume Index (PVI)",
    category="Volume",
    description=(
        "Cumulative price-change tracker on volume-UP days "
        "only (Fosback's 'Dumb Money' / retail-flow line). "
        "Companion to NVI."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "PVI sirf volume-up days ka price action accumulate "
        "karta hai — Fosback ki theory: retail flow high-volume "
        "days pe dominate karta hai. NVI ke saath pair karke use "
        "karte hain."
    ),
    tags=["volume", "fosback"],
    calculation_function="positive_volume_index",
)


# ─── Microstructure (4) ──────────────────────────────────────────────


_TRUE_STRENGTH_INDEX = IndicatorMetadata(
    id="true_strength_index",
    name="True Strength Index (TSI)",
    category="Momentum",
    description=(
        "Double-smoothed price-change momentum (William Blau, "
        "1991). Pine equivalent ``ta.tsi``. Range roughly "
        "``[-100, +100]``."
    ),
    inputs=[
        InputSpec(name="long", type=InputType.NUMBER, default=25, min=2, max=200),
        InputSpec(name="short", type=InputType.NUMBER, default=13, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.tsi"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "TSI MACD ka double-smoothed cousin — price changes ko "
        "twice EMA-smooth karke ratio nikalta hai. Zero ke upar "
        "= bullish momentum, neeche = bearish."
    ),
    tags=["momentum"],
    calculation_function="true_strength_index",
)


_PERCENT_PRICE_OSCILLATOR = IndicatorMetadata(
    id="percent_price_oscillator",
    name="Percentage Price Oscillator (PPO)",
    category="Momentum",
    description=(
        "MACD's % cousin — ``(EMA(fast) - EMA(slow)) / "
        "EMA(slow) * 100``. Pine equivalent ``ta.ppo``. Comparable "
        "across symbols / timeframes (MACD's absolute units "
        "aren't)."
    ),
    inputs=[
        InputSpec(name="fast", type=InputType.NUMBER, default=12, min=2, max=200),
        InputSpec(name="slow", type=InputType.NUMBER, default=26, min=3, max=400),
        InputSpec(name="signal", type=InputType.NUMBER, default=9, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.ppo"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "PPO MACD ka percentage version — readings cross-symbol "
        "comparable hain. Zero crossover = trend change signal."
    ),
    tags=["momentum"],
    calculation_function="percent_price_oscillator",
)


_RATE_OF_CHANGE_VOLUME = IndicatorMetadata(
    id="rate_of_change_volume",
    name="Volume Rate-of-Change",
    category="Volume",
    description=(
        "ROC applied to volume rather than price. Useful as a "
        "confirmation filter — real breakouts typically show "
        "positive volume ROC."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Volume ROC volume change % batata hai. Price breakout "
        "ke saath positive volume ROC = high-conviction signal."
    ),
    tags=["volume", "momentum"],
    calculation_function="rate_of_change_volume",
)


_NEGATIVE_VOLUME_INDEX = IndicatorMetadata(
    id="negative_volume_index",
    name="Negative Volume Index (NVI)",
    category="Volume",
    description=(
        "Cumulative price-change tracker on volume-DOWN days "
        "only (Paul Dysart 1936 / Norman Fosback 1976). "
        "Fosback's 'Smart Money' / institutional-flow line."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "NVI sirf volume-down days ka price action capture karta "
        "hai — institutional flow track karne ka tarika. Rising "
        "NVI in low-volume days = quiet accumulation."
    ),
    tags=["volume", "fosback"],
    calculation_function="negative_volume_index",
)


# ─── Order Flow Proxy (4) ────────────────────────────────────────────


_MONEY_FLOW_RATIO = IndicatorMetadata(
    id="money_flow_ratio",
    name="Money Flow Ratio",
    category="Volume",
    description=(
        "Up-money / down-money raw ratio over a rolling window "
        "— underpins MFI but exposed unnormalised so strategies "
        "can branch on it directly. Returns +inf when down-money "
        "is zero (operator branches expected to handle)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Money Flow Ratio raw form mein — MFI ke 0-100 "
        "normalisation ke bina. >2 = strong buying pressure, "
        "<0.5 = strong selling. Inf handle karna padta hai jab "
        "down-money zero ho."
    ),
    tags=["volume", "flow"],
    calculation_function="money_flow_ratio",
)


_ON_BALANCE_VOLUME_EMA = IndicatorMetadata(
    id="on_balance_volume_ema",
    name="OBV — EMA Smoothed",
    category="Volume",
    description=(
        "On-Balance Volume passed through an EMA. Crossings of "
        "OBV vs the smoothed line are classic Granville signals."
    ),
    inputs=[
        InputSpec(
            name="ema_period", type=InputType.NUMBER, default=21, min=2, max=200,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "OBV EMA-smoothed = noise reduce karta hai. Raw OBV vs "
        "smoothed OBV crossover = Granville's classic signal."
    ),
    tags=["volume", "smoothed"],
    calculation_function="on_balance_volume_ema",
)


_CUMULATIVE_VOLUME_DELTA = IndicatorMetadata(
    id="cumulative_volume_delta",
    name="Cumulative Volume Delta (proxy)",
    category="Volume",
    description=(
        "Cumulative running total of bar-direction-signed "
        "volume. Real CVD needs bid/ask tape — this is the "
        "retail-platform proxy that signs by ``close >= open``."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "CVD proxy = bullish bars ka volume + minus bearish bars "
        "ka volume cumulative. Real CVD bid/ask tape se hota hai "
        "(TRADETRI ke pas Phase 1 mein nahi); proxy retail "
        "convention hai."
    ),
    tags=["volume", "flow", "proxy"],
    calculation_function="cumulative_volume_delta",
)


_BUYING_PRESSURE_RATIO = IndicatorMetadata(
    id="buying_pressure_ratio",
    name="Buying Pressure Ratio",
    category="Volume",
    description=(
        "Fraction of rolling-window volume on bullish bars. "
        "Range ``[0, 1]``. > 0.5 = buyers dominate the window; "
        "< 0.5 = sellers dominate."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=20, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Buying Pressure Ratio bullish bars ke volume ka window "
        "share. 0.6+ = buyers strong, 0.4- = sellers strong. "
        "Trend confirmation filter ke liye good."
    ),
    tags=["volume", "pressure"],
    calculation_function="buying_pressure_ratio",
)


# ─── Aggregate ─────────────────────────────────────────────────────────


PACK10_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _VOLUME_WEIGHTED_AVG_CLOSE,
    _VOLUME_AT_PRICE_HIGH,
    _VOLUME_BREAKOUT,
    _POSITIVE_VOLUME_INDEX,
    _TRUE_STRENGTH_INDEX,
    _PERCENT_PRICE_OSCILLATOR,
    _RATE_OF_CHANGE_VOLUME,
    _NEGATIVE_VOLUME_INDEX,
    _MONEY_FLOW_RATIO,
    _ON_BALANCE_VOLUME_EMA,
    _CUMULATIVE_VOLUME_DELTA,
    _BUYING_PRESSURE_RATIO,
)


__all__ = ["PACK10_ACTIVE_INDICATORS"]
