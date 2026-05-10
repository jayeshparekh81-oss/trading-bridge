"""Pack 8 — 12 multi-timeframe + specialty + India-specific indicators.

All 12 ids are net-new (no collisions detected during discovery).

Two indicators ship with intentional caveats documented up-front
rather than buried in their calc-module docstrings:

* ``nifty_correlation`` is a Phase-1 STUB that returns an
  all-``None`` series. The real implementation needs the data-
  provider layer to expose a "fetch comparison series for the
  same window" helper at the calc-layer abstraction; that
  cross-cutting wiring is a Phase-2 item. Strategies referencing
  it get a defined-shape placeholder they can branch on
  (``is None`` → "data not yet available"). The
  :data:`HAS_MARKET_CONTEXT` flag in the calc module is the
  operator-visible signal.

* ``opening_range_breakout`` requires intraday timestamps. When
  the input candles are daily-or-larger frequency the function
  returns an all-``None`` series rather than raising — the UI
  should surface a "ORB needs intraday data" hint. Detection is
  by inter-bar timestamp gap.

* ``ehlers_fisher`` is the Inverse-Fisher-Transform-of-RSI
  variant — distinct from the standard Pack-7 ``fisher_transform``
  (which applies the Fisher transform to *price* directly).

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT — schema has no
ADVANCED tier; spec's "ADVANCED" mapped to EXPERT):

    INTERMEDIATE (8) — mtf_ema_alignment, higher_high_lower_low,
                       swing_failure, weekly_pivot_close,
                       gap_up_down, daily_pivot_distance,
                       zigzag, mcginley_dynamic
    EXPERT (4)       — opening_range_breakout, nifty_correlation,
                       fractal_chaos_bands, ehlers_fisher

Pine importer: no entries. None of the Pack-8 indicators have a
standard Pine v5 ``ta.*`` equivalent — they're all custom
formulations or India-specific concepts.
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

# ─── Multi-timeframe / Cross-period (4) ───────────────────────────────


_MTF_EMA_ALIGNMENT = IndicatorMetadata(
    id="mtf_ema_alignment",
    name="Multi-Timeframe EMA Alignment",
    category="Trend",
    description=(
        "+1 / 0 / -1 alignment score over a stack of EMA periods "
        "(default 20 / 50 / 200). All ascending → +1; all "
        "descending → -1; mixed → 0."
    ),
    inputs=[
        InputSpec(
            name="periods", type=InputType.STRING, default="20,50,200",
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MTF EMA Alignment 3 EMAs ka direction agreement check "
        "karta hai. +1 = strong uptrend confirmation, -1 = strong "
        "downtrend, 0 = chop / regime change."
    ),
    tags=["trend", "mtf"],
    calculation_function="mtf_ema_alignment",
)


_HIGHER_HIGH_LOWER_LOW = IndicatorMetadata(
    id="higher_high_lower_low",
    name="Higher High / Lower Low Pattern",
    category="Pattern",
    description=(
        "+1 if current bar prints HH + HL vs trailing window. "
        "-1 if it prints LH + LL. 0 otherwise."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=5, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "HH/LL pattern textbook trend continuation signal. "
        "Sustained +1 = uptrend continuation, sustained -1 = "
        "downtrend continuation."
    ),
    tags=["pattern", "structure"],
    calculation_function="higher_high_lower_low",
)


_SWING_FAILURE = IndicatorMetadata(
    id="swing_failure",
    name="Swing Failure Pattern",
    category="Pattern",
    description=(
        "Detects bars that pierced a prior swing extreme but "
        "closed back inside the range — bull-trap / bear-trap "
        "reversal candidates."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=10, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Swing Failure jab price prior high/low pierce kare lekin "
        "close inside ho jaaye — bull-trap (sell) ya bear-trap "
        "(buy) reversal signal."
    ),
    tags=["pattern", "reversal"],
    calculation_function="swing_failure",
)


_WEEKLY_PIVOT_CLOSE = IndicatorMetadata(
    id="weekly_pivot_close",
    name="Weekly Pivot Distance",
    category="Pivot",
    description=(
        "% distance between the current close and the prior "
        "completed week's classic pivot (H+L+C)/3. Forward-look-"
        "safe (uses prior week only)."
    ),
    inputs=[
        InputSpec(
            name="weeks_back", type=InputType.NUMBER, default=1, min=1, max=12,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Weekly Pivot Distance batata hai close pichla hafta ke "
        "pivot se kitna door hai. Strong directional move ke "
        "regimes mein useful filter."
    ),
    tags=["pivot", "weekly"],
    calculation_function="weekly_pivot_close",
)


# ─── India-specific (4) ──────────────────────────────────────────────


_OPENING_RANGE_BREAKOUT = IndicatorMetadata(
    id="opening_range_breakout",
    name="Opening Range Breakout (ORB)",
    category="India-Specific",
    description=(
        "+1 / -1 / 0 code based on close vs first-N-minute "
        "opening-range high / low. Default 15-min ORB. **Needs "
        "intraday timestamps** — daily-or-larger frequency "
        "returns an all-None series."
    ),
    inputs=[
        InputSpec(
            name="range_minutes", type=InputType.NUMBER, default=15, min=1, max=120,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ORB India retail ka classic intraday signal. First 15 "
        "min ka high break = long, low break = short. Daily "
        "candles pe nahi chalta — intraday timeframe choose karo."
    ),
    tags=["india", "intraday", "breakout"],
    calculation_function="opening_range_breakout",
)


_GAP_UP_DOWN = IndicatorMetadata(
    id="gap_up_down",
    name="Gap Up/Down Classifier",
    category="India-Specific",
    description=(
        "+1 / -1 / 0 per-bar based on opening gap vs prior "
        "close, threshold in % of prior close (default 0.5 %)."
    ),
    inputs=[
        InputSpec(
            name="threshold_pct", type=InputType.NUMBER,
            default=0.5, min=0.01, max=20.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Gap Up/Down classifier overnight news + global cues "
        "ke effect ko quantify karta hai. India market mein "
        "morning gap pe entry timing ke liye useful."
    ),
    tags=["india", "gap"],
    calculation_function="gap_up_down",
)


_DAILY_PIVOT_DISTANCE = IndicatorMetadata(
    id="daily_pivot_distance",
    name="Daily Pivot Distance",
    category="Pivot",
    description=(
        "% distance between the current close and the prior "
        "trading day's classic pivot (H+L+C)/3. Forward-look-"
        "safe."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Daily Pivot Distance prior-day pivot se distance batata "
        "hai. Pivot ke aas-paas reversal-prone, dur jane par "
        "trend-continuation tendency."
    ),
    tags=["pivot", "daily"],
    calculation_function="daily_pivot_distance",
)


_NIFTY_CORRELATION = IndicatorMetadata(
    id="nifty_correlation",
    name="NIFTY Correlation (stub)",
    category="India-Specific",
    description=(
        "Rolling Pearson correlation of close against NIFTY. "
        "**Phase 1 STUB** — returns an all-None series until the "
        "data-provider layer exposes a comparison-series fetch "
        "(Phase 2). The signature is final; only the body changes."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "NIFTY Correlation stock vs broader market relationship "
        "dikhata hai. Phase 1 mein abhi stub hai (data-provider "
        "wiring Phase 2 mein aayega) — None series milega tab "
        "tak."
    ),
    tags=["india", "correlation", "stub"],
    calculation_function="nifty_correlation",
)


# ─── Specialty / Advanced (4) ────────────────────────────────────────


_ZIGZAG = IndicatorMetadata(
    id="zigzag",
    name="ZigZag",
    category="Pattern",
    description=(
        "Marks confirmed turning points (+1 = swing low, -1 = "
        "swing high, 0 = not a turn) once price reverses by "
        "deviation_pct from the prior extreme."
    ),
    inputs=[
        InputSpec(
            name="deviation_pct", type=InputType.NUMBER,
            default=5.0, min=0.1, max=50.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ZigZag swing highs/lows mark karta hai jab price "
        "deviation_pct se reverse ho. Note: confirmation lag "
        "hota hai — real-time entry signal nahi, post-hoc "
        "structure marker."
    ),
    tags=["pattern", "swing"],
    calculation_function="zigzag",
)


_FRACTAL_CHAOS_BANDS = IndicatorMetadata(
    id="fractal_chaos_bands",
    name="Fractal Chaos Bands (Upper)",
    category="Volatility",
    description=(
        "Upper band of the Williams-fractal envelope — tracks the "
        "most-recent 5-bar fractal high within the trailing "
        "period. Lower band is a separate registry config."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=9, min=5, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Fractal Chaos Bands recent 5-bar fractal extremes ko "
        "envelope karta hai. Breakout above upper band = trend "
        "continuation signal."
    ),
    tags=["volatility", "fractal"],
    calculation_function="fractal_chaos_bands",
)


_EHLERS_FISHER = IndicatorMetadata(
    id="ehlers_fisher",
    name="Ehlers Inverse Fisher of RSI",
    category="Momentum",
    description=(
        "Inverse Fisher transform applied to RSI: maps RSI into "
        "``[-1, +1]`` so extremes become statistically rare. "
        "Distinct from Pack-7 ``fisher_transform`` (which "
        "applies Fisher to price)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Ehlers Inverse Fisher RSI ke extremes ko sharp signals "
        "mein convert karta hai. Near +1 = overbought (sell), "
        "near -1 = oversold (buy)."
    ),
    tags=["momentum", "ehlers"],
    calculation_function="ehlers_fisher",
)


_MCGINLEY_DYNAMIC = IndicatorMetadata(
    id="mcginley_dynamic",
    name="McGinley Dynamic",
    category="Trend",
    description=(
        "Self-tuning moving average that responds faster in up-"
        "trends and slower in down-trends than a fixed-period "
        "EMA. Reduces whipsaw on volatile markets."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(
            name="constant", type=InputType.NUMBER,
            default=0.6, min=0.1, max=2.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "McGinley Dynamic adaptive MA — uptrend mein fast, "
        "downtrend mein slow. EMA whipsaws kam karta hai jab "
        "volatility spike ho."
    ),
    tags=["trend", "adaptive"],
    calculation_function="mcginley_dynamic",
)


# ─── Aggregate ─────────────────────────────────────────────────────────


PACK8_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _MTF_EMA_ALIGNMENT,
    _HIGHER_HIGH_LOWER_LOW,
    _SWING_FAILURE,
    _WEEKLY_PIVOT_CLOSE,
    _OPENING_RANGE_BREAKOUT,
    _GAP_UP_DOWN,
    _DAILY_PIVOT_DISTANCE,
    _NIFTY_CORRELATION,
    _ZIGZAG,
    _FRACTAL_CHAOS_BANDS,
    _EHLERS_FISHER,
    _MCGINLEY_DYNAMIC,
)


__all__ = ["PACK8_ACTIVE_INDICATORS"]
