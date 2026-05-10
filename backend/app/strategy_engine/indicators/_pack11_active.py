"""Pack 11 — 12 cycle + divergence + advanced pattern indicators.

No discovery-time collisions. The Pack-4 active ``inside_bar``
exists but is structurally different from Pack-11's
``inside_bar_breakout`` (single boolean vs paired-with-direction
on the next bar) — both can coexist.

No Pine importer wiring this pack — none of the Pack-11
indicators have a standard Pine v5 ``ta.*`` equivalent. The
cycle indicators are Ehlers' published designs (custom
implementations); the divergence detectors are common-knowledge
pattern matches with no Pine builtin; the advanced patterns are
all custom formulations or trader-knowledge concepts.

Difficulty split:

    INTERMEDIATE (5) — cycle_period_oscillator, inside_bar_breakout,
                       outside_bar, nr7, wide_range_bar
    EXPERT (7)       — dominant_cycle_period, mesa_sine_wave,
                       mesa_sine_lead, rsi_divergence,
                       macd_divergence, obv_divergence,
                       consolidation_score

Two scope-honesty notes documented in the calc modules + here:

* The MESA family + dominant_cycle_period use a *simplified*
  Hilbert-discriminator (kept the in-phase / quadrature
  decomposition; skipped Ehlers' median-period chain). Numeric
  output won't byte-match TradingView's stock template — but it
  delivers the qualitative signal Ehlers intended (cycle period
  + sine/lead crossings).
* Divergence detection is the "regular" textbook variety — new
  price extreme that the indicator fails to confirm. Hidden
  divergence (a different concept) is deferred to v1.1; the
  current detector returns 0 for those bars.
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

# ─── Cycle Indicators (4) ─────────────────────────────────────────────


_DOMINANT_CYCLE_PERIOD = IndicatorMetadata(
    id="dominant_cycle_period",
    name="Dominant Cycle Period",
    category="Cycle",
    description=(
        "Hilbert-Transform-Discriminator estimate of the dominant "
        "cycle's period (John Ehlers, 2001). Output is the "
        "period in bars (typically 6-50). Useful as an adaptive "
        "input to other indicators."
    ),
    inputs=[
        InputSpec(name="smooth", type=InputType.NUMBER, default=0.07, min=0.01, max=1.0),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Dominant Cycle Period market ka current cycle length "
        "estimate karta hai. Trending markets mein high (40+), "
        "choppy mein low (10-15). Adaptive period input ke liye."
    ),
    tags=["cycle", "ehlers"],
    calculation_function="dominant_cycle_period",
)


_MESA_SINE_WAVE = IndicatorMetadata(
    id="mesa_sine_wave",
    name="MESA Sine Wave",
    category="Cycle",
    description=(
        "Sine-wave projection of the dominant-cycle phase "
        "(Ehlers 1992). Range ``[-1, +1]``. Pair with "
        "``mesa_sine_lead`` for crossover signals."
    ),
    inputs=[
        InputSpec(name="alpha", type=InputType.NUMBER, default=0.07, min=0.01, max=1.0),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MESA Sine Wave dominant cycle ka phase plot karta hai. "
        "Lead wave ke saath crossover = cycle turn 1/8 cycle "
        "ahead of actual reversal."
    ),
    tags=["cycle", "ehlers", "mesa"],
    calculation_function="mesa_sine_wave",
)


_MESA_SINE_LEAD = IndicatorMetadata(
    id="mesa_sine_lead",
    name="MESA Sine Lead",
    category="Cycle",
    description=(
        "45° (π/4) phase-leading projection of the dominant-cycle "
        "phase. Companion to ``mesa_sine_wave``."
    ),
    inputs=[
        InputSpec(name="alpha", type=InputType.NUMBER, default=0.07, min=0.01, max=1.0),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MESA Sine Lead = sine wave + 45° lead. Sine wave ko "
        "cross karne pe early turning-point signal."
    ),
    tags=["cycle", "ehlers", "mesa"],
    calculation_function="mesa_sine_lead",
)


_CYCLE_PERIOD_OSCILLATOR = IndicatorMetadata(
    id="cycle_period_oscillator",
    name="Cycle Period Oscillator",
    category="Cycle",
    description=(
        "Period-normalised position of close inside the trailing "
        "high/low envelope. Range ``[-1, +1]``. Simpler cousin "
        "of MESA without Hilbert dependency."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Cycle Period Oscillator close ka relative position "
        "trailing window mein -1 to +1 mein map karta hai. "
        "Stochastic %K ka -1..+1 version, cycle strategies ke liye."
    ),
    tags=["cycle", "oscillator"],
    calculation_function="cycle_period_oscillator",
)


# ─── Divergence Detection (3) ─────────────────────────────────────────


_RSI_DIVERGENCE = IndicatorMetadata(
    id="rsi_divergence",
    name="RSI Divergence",
    category="Divergence",
    description=(
        "+1 (bullish) / -1 (bearish) / 0 per-bar code based on "
        "price vs RSI 'regular' divergence over a trailing window."
    ),
    inputs=[
        InputSpec(name="rsi_period", type=InputType.NUMBER, default=14, min=2, max=200),
        InputSpec(name="lookback", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "RSI Divergence price ne nayi high/low banaya but RSI "
        "ne confirm nahi kiya — reversal warning. Bullish (+1) "
        "ya bearish (-1) ke saath aata hai."
    ),
    tags=["divergence", "rsi"],
    calculation_function="rsi_divergence",
)


_MACD_DIVERGENCE = IndicatorMetadata(
    id="macd_divergence",
    name="MACD Divergence",
    category="Divergence",
    description=(
        "+1 / -1 / 0 per-bar code based on price vs MACD-line "
        "divergence over a trailing window. ``signal`` parameter "
        "kept for shape parity with standard MACD config."
    ),
    inputs=[
        InputSpec(name="fast", type=InputType.NUMBER, default=12, min=2, max=200),
        InputSpec(name="slow", type=InputType.NUMBER, default=26, min=3, max=400),
        InputSpec(name="signal", type=InputType.NUMBER, default=9, min=2, max=200),
        InputSpec(name="lookback", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "MACD Divergence price ka extreme MACD line ne match "
        "nahi kiya = trend exhaustion ka signal. Reversal "
        "candidates ke liye highest-conviction filter."
    ),
    tags=["divergence", "macd"],
    calculation_function="macd_divergence",
)


_OBV_DIVERGENCE = IndicatorMetadata(
    id="obv_divergence",
    name="OBV Divergence",
    category="Divergence",
    description=(
        "+1 / -1 / 0 per-bar code based on price vs OBV "
        "divergence — 'smart money / dumb money' under-the-"
        "surface signal."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "OBV Divergence price ne nayi high/low banaya but OBV "
        "ne support nahi kiya = under-the-surface "
        "distribution / accumulation signal."
    ),
    tags=["divergence", "volume"],
    calculation_function="obv_divergence",
)


# ─── Advanced Patterns (5) ────────────────────────────────────────────


_INSIDE_BAR_BREAKOUT = IndicatorMetadata(
    id="inside_bar_breakout",
    name="Inside-Bar Breakout",
    category="Pattern",
    description=(
        "+1 (long) / -1 (short) / 0 per-bar code emitted one bar "
        "after an inside bar — pairs the inside-bar setup with "
        "the next bar's breakout direction. Distinct from Pack-4's "
        "structural ``inside_bar`` boolean."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Inside Bar Breakout = inside bar ke baad ke bar mein "
        "high/low cross hua. Direct entry signal — long ya "
        "short."
    ),
    tags=["pattern", "breakout"],
    calculation_function="inside_bar_breakout",
)


_OUTSIDE_BAR = IndicatorMetadata(
    id="outside_bar",
    name="Outside Bar",
    category="Pattern",
    description=(
        "+1 (bullish-close) / -1 (bearish-close) / 0 per-bar "
        "code. An outside bar strictly engulfs the prior bar's "
        "high/low range."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Outside Bar = current bar prior bar ka range engulf "
        "kare. Bullish close = +1, bearish = -1. Strong "
        "momentum + reversal signal."
    ),
    tags=["pattern", "engulfing"],
    calculation_function="outside_bar",
)


_NR7 = IndicatorMetadata(
    id="nr7",
    name="Narrowest Range 7 (NR7)",
    category="Pattern",
    description=(
        "+1 if the bar's range is the narrowest of the last 7 "
        "bars; 0 otherwise. Tony Crabel's compression / pre-"
        "breakout signal."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "NR7 = pichla 7 bars mein sabse narrow range. "
        "Compression build up — breakout aane wala hai. "
        "Direction predict nahi karta — bas compression flag."
    ),
    tags=["pattern", "compression"],
    calculation_function="nr7",
)


_WIDE_RANGE_BAR = IndicatorMetadata(
    id="wide_range_bar",
    name="Wide-Range Bar",
    category="Pattern",
    description=(
        "+1 / -1 / 0 per-bar code. Range > mult x rolling-avg "
        "range with bullish close = +1, bearish close = -1."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(name="mult", type=InputType.NUMBER, default=1.5, min=0.5, max=10.0),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Wide Range Bar = avg range se bahut bada bar. "
        "Conviction-driven move — direction (close vs open) "
        "ke saath signal aata hai."
    ),
    tags=["pattern", "expansion"],
    calculation_function="wide_range_bar",
)


_CONSOLIDATION_SCORE = IndicatorMetadata(
    id="consolidation_score",
    name="Consolidation Score",
    category="Pattern",
    description=(
        "Multi-bar tightness measure in ``[0, 1]``. 1.0 = very "
        "tight consolidation; 0.0 = wide / trending. Useful as a "
        "pre-breakout regime filter."
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
        "Consolidation Score window kitna tight hai measure "
        "karta hai (avg_range / window_range). 0.7+ = strong "
        "consolidation, breakout setup ke liye filter."
    ),
    tags=["pattern", "regime"],
    calculation_function="consolidation_score",
)


# ─── Aggregate ─────────────────────────────────────────────────────────


PACK11_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _DOMINANT_CYCLE_PERIOD,
    _MESA_SINE_WAVE,
    _MESA_SINE_LEAD,
    _CYCLE_PERIOD_OSCILLATOR,
    _RSI_DIVERGENCE,
    _MACD_DIVERGENCE,
    _OBV_DIVERGENCE,
    _INSIDE_BAR_BREAKOUT,
    _OUTSIDE_BAR,
    _NR7,
    _WIDE_RANGE_BAR,
    _CONSOLIDATION_SCORE,
)


__all__ = ["PACK11_ACTIVE_INDICATORS"]
