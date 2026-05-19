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


_RANDOM_WALK_INDEX = IndicatorMetadata(
    id="random_walk_index",
    name="Random Walk Index (RWI)",
    category="Trend",
    description=(
        "Michael Poulos' RWI — measures how far price has moved relative "
        "to what a random walk would produce. Two outputs: RWI_high "
        "(uptrend strength) and RWI_low (downtrend strength). Sweeps "
        "lookback windows 2..max_length and returns the per-bar max. "
        "Defaults: max_length=10, atr_period=10."
    ),
    inputs=[
        InputSpec(name="max_length", type=InputType.NUMBER, default=10, min=2, max=50),
        InputSpec(name="atr_period", type=InputType.NUMBER, default=10, min=2, max=200),
    ],
    outputs=["rwi_high", "rwi_low"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "RWI > 1 trend confirm karta — actual price-move random-walk "
        "expected move se zyada. RWI_high dominate kare = uptrend; "
        "RWI_low dominate = downtrend. Both < 1 mein = ranging market."
    ),
    tags=["trend", "random-walk", "library-canonical"],
    calculation_function="random_walk_index",
)


_EOM = IndicatorMetadata(
    id="eom",
    name="Ease of Movement (EOM)",
    category="Volume",
    description=(
        "Richard Arms' Ease of Movement — how easily price moves "
        "relative to volume. ``midpoint_move / box_ratio``, "
        "SMA-smoothed. Pine ``ta.eom(14, 10000)`` parity."
    ),
    inputs=[
        InputSpec(name="length", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(name="divisor", type=InputType.NUMBER, default=10000, min=1, max=1000000),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.eom"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "EOM batata price kitna 'easily' move karta — big move on small "
        "volume = high EOM, big volume on small move = low EOM. "
        "Trend-quality filter ke roop mein use hota — rising EOM trend "
        "ko healthy mark karta."
    ),
    tags=["volume", "ease-of-movement", "library-canonical"],
    calculation_function="eom",
)


_TSI = IndicatorMetadata(
    id="tsi",
    name="True Strength Index (TSI)",
    category="Momentum",
    description=(
        "William Blau's True Strength Index — double-smoothed momentum "
        "ratio. ``TSI = 100 * EMA(EMA(PC, long), short) / EMA(EMA(|PC|, "
        "long), short)`` where PC = close - close[1]. Pine ``ta.tsi`` "
        "parity. Default long=25, short=13."
    ),
    inputs=[
        InputSpec(name="long_period", type=InputType.NUMBER, default=25, min=2, max=500),
        InputSpec(name="short_period", type=InputType.NUMBER, default=13, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.tsi"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "TSI MACD ka double-smoothed cousin hai. Momentum direction + "
        "strength ek number mein. Zero-line cross trend-shift; "
        "divergence-watch karne ke liye sabse popular indicator."
    ),
    tags=["momentum", "double-smoothed", "library-canonical"],
    calculation_function="tsi",
)


_DEMARKER = IndicatorMetadata(
    id="demarker",
    name="DeMarker (DeM)",
    category="Momentum",
    description=(
        "Tom DeMark's DeMarker — bounded 0..1 overbought/oversold "
        "oscillator. Smoothed ratio of new-high pressure (DeMax) over "
        "total new-high + new-low pressure (DeMax + DeMin). >0.7 reads "
        "overbought; <0.3 reads oversold."
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
        "DeMarker 0-1 mein bounded — 0.7 ke upar overbought, 0.3 ke "
        "neeche oversold. RSI ke alternative, slightly cleaner signals "
        "kyunki bar-extension pressure use karta (close-to-close nahi)."
    ),
    tags=["momentum", "oscillator", "library-canonical"],
    calculation_function="demarker",
)


_ACCELERATOR_OSCILLATOR = IndicatorMetadata(
    id="accelerator_oscillator",
    name="Accelerator Oscillator (AC)",
    category="Momentum",
    description=(
        "Bill Williams' Accelerator Oscillator — second-derivative-style "
        "momentum read. AC = AO - SMA(AO, ac_smoothing). Where AO reads "
        "momentum velocity, AC reads momentum acceleration: it flips "
        "before AO does, giving an earlier (but noisier) read."
    ),
    inputs=[
        InputSpec(name="ao_fast", type=InputType.NUMBER, default=5, min=1, max=200),
        InputSpec(name="ao_slow", type=InputType.NUMBER, default=34, min=2, max=500),
        InputSpec(name="ac_smoothing", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "AC AO se faster react karta — acceleration phase mein flip pehle "
        "hota. Bill Williams ki trading-chaos toolkit ka core indicator. "
        "AO ke saath pair karke use karo, akela noisy hota."
    ),
    tags=["momentum", "bill-williams", "library-canonical"],
    calculation_function="accelerator_oscillator",
)


_WILLIAMS_VIX_FIX = IndicatorMetadata(
    id="williams_vix_fix",
    name="Williams VIX Fix",
    category="Volatility",
    description=(
        "Larry Williams' VIX Fix — synthetic VIX-like volatility for any "
        "OHLC stream. ``((highest_high[period] - low[today]) / "
        "highest_high[period]) * 100``. Spikes flag capitulation moments; "
        "commonly used for long-side mean-reversion entries near market "
        "lows. Default period 22 per Williams' original (2007)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=22, min=1, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "WVF synthetic VIX hai — koi bhi stock pe lagao, capitulation "
        "moments visible ho jaate. Spike upar = fear extreme = "
        "long-side mean-reversion setup banta hai. Pair Bollinger Bands "
        "ya percentile filter ke saath."
    ),
    tags=["volatility", "vix", "library-canonical"],
    calculation_function="williams_vix_fix",
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
    _WILLIAMS_VIX_FIX,
    _ACCELERATOR_OSCILLATOR,
    _DEMARKER,
    _TSI,
    _EOM,
    _RANDOM_WALK_INDEX,
)


__all__ = ["PACK_COMPLETION_WAVE1_ACTIVE_INDICATORS"]
