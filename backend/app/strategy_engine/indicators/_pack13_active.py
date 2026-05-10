"""Pack 13 - 12 sentiment + breadth + cross-asset indicators.

Discovery-time naming-overlap (handled honestly):

    * ``bull_bear_power`` would have overloaded Elder's "Bull
      Power" / "Bear Power" terminology (Pack 6's
      ``elder_ray_bull`` / ``elder_ray_bear``). Even though the
      mechanism is different, the naming would mislead users.
      -> substituted with ``breadth_thrust`` (Marty Zweig's
        classic, single-symbol proxy: 10-day EMA of the bullish-
        bar share). Distinct concept, well-known name.

Honest Phase-1 stub (Pack 8 lesson):

    * ``relative_strength_vs_benchmark`` requires a benchmark
      candle series at the calc-layer abstraction. The data-
      provider doesn't expose that yet (same crossing as the
      Pack 8 ``nifty_correlation`` stub). Ships as a no-op
      returning all-``None``, with ``HAS_BENCHMARK_CONTEXT =
      False`` flag for the dashboard. Test asserts the contract
      so a Phase-2 wiring can't quietly regress.

Honest scope notes:

    * ``mcclellan_oscillator_proxy`` and ``trin_proxy`` and
      ``advance_decline_proxy`` and ``tick_index`` are
      single-symbol proxies of inherently market-wide indicators.
      Documented in each calc module's header. Useful as
      sentiment-shape signals; won't byte-match the exchange-
      wide originals.
    * ``fear_greed_index`` is a 3-factor composite (momentum,
      volatility, flow) chosen from data we have at the calc
      layer. CNN's headline F&G uses 7 inputs we don't have
      access to at this abstraction (put/call, VIX, junk-bond
      demand, etc.).
    * ``trend_consistency_score`` is a *continuous* relative of
      Pack 8's ternary ``mtf_ema_alignment``. Both can coexist;
      different output shapes for different decision needs.
    * ``correlation_with_volume`` is a convenience wrapper over
      Pack 4's ``correlation_coefficient`` formula with fixed
      inputs (close, volume) - useful named indicator for the
      common "is price moving with volume?" question.

NO new Pine importer wiring - none of Pack 13's indicators have
a standard Pine v5 ``ta.*`` equivalent. Lock test
``test_pack13_has_no_pine_aliases`` pins the contract.

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT):

    INTERMEDIATE (6) - fear_greed_index, breadth_thrust,
                       sentiment_oscillator, tick_index,
                       advance_decline_proxy,
                       correlation_with_volume
    EXPERT (6)       - capitulation_signal,
                       mcclellan_oscillator_proxy, trin_proxy,
                       relative_strength_vs_benchmark (stub),
                       divergence_strength_score,
                       trend_consistency_score
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

# --- Sentiment Proxies (4) ------------------------------------------


_FEAR_GREED_INDEX = IndicatorMetadata(
    id="fear_greed_index",
    name="Fear & Greed Index",
    category="Sentiment",
    description=(
        "0-100 composite proxy combining momentum (RSI), "
        "volatility (ATR percentile), and flow (OBV slope). "
        "0 = extreme fear, 100 = extreme greed. Single-symbol "
        "approximation of CNN's market-wide F&G."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=30, min=5, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Fear & Greed Index 3 factors combine karta hai - momentum, "
        "volatility, flow. <30 = extreme fear (contrarian buy "
        "candidate), >70 = extreme greed (caution / mean-reversion)."
    ),
    tags=["sentiment", "composite"],
    calculation_function="fear_greed_index",
)


_BREADTH_THRUST = IndicatorMetadata(
    id="breadth_thrust",
    name="Breadth Thrust (Zweig)",
    category="Sentiment",
    description=(
        "Single-symbol proxy of Marty Zweig's classic. EMA of "
        "rolling bullish-bar share. Range [0, 1]; readings rising "
        "from <0.40 to >0.615 within ~10 bars flag a major buy."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=2, max=200),
        InputSpec(
            name="ema_period", type=InputType.NUMBER, default=10, min=2, max=200,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Breadth Thrust = bullish bars ka rolling share, smoothed. "
        "Strong rally start ka classic Zweig signal: 0.4 se 0.615 "
        "10 bars mein cross karna."
    ),
    tags=["sentiment", "breadth"],
    calculation_function="breadth_thrust",
)


_SENTIMENT_OSCILLATOR = IndicatorMetadata(
    id="sentiment_oscillator",
    name="Sentiment Oscillator",
    category="Sentiment",
    description=(
        "Per-bar % of bullish bars (close >= open) in the "
        "trailing window. Range [0, 100]."
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
        "Sentiment Oscillator = bullish bars ka % rolling. >70 "
        "= persistent bullish; <30 = persistent bearish. Trend "
        "confirmation filter."
    ),
    tags=["sentiment"],
    calculation_function="sentiment_oscillator",
)


_CAPITULATION_SIGNAL = IndicatorMetadata(
    id="capitulation_signal",
    name="Capitulation Signal",
    category="Sentiment",
    description=(
        "+1 / -1 / 0 per-bar code for panic / climax bars. "
        "Volume + range spike with close at the bar's extreme = "
        "capitulation (contrarian / mean-reversion candidate)."
    ),
    inputs=[
        InputSpec(name="vol_mult", type=InputType.NUMBER, default=3.0, min=1.0, max=20.0),
        InputSpec(name="range_mult", type=InputType.NUMBER, default=2.0, min=1.0, max=10.0),
        InputSpec(name="lookback", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(
            name="close_position_threshold", type=InputType.NUMBER,
            default=0.85, min=0.5, max=1.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Capitulation Signal = panic bars - vol spike + range "
        "spike + close near extreme. Contrarian signal (panic "
        "= short-term exhaustion)."
    ),
    tags=["sentiment", "extreme"],
    calculation_function="capitulation_signal",
)


# --- Market Breadth Proxies (4) -------------------------------------


_TICK_INDEX = IndicatorMetadata(
    id="tick_index",
    name="Tick Index (proxy)",
    category="Breadth",
    description=(
        "Net up-tick proxy: sum of bar directions (close vs prior "
        "close) over the trailing window. Range [-period, +period]."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Tick Index single-symbol proxy = close-to-close direction "
        "ka net count. NYSE Tick ka shape — exchange-wide nahi, "
        "single symbol per."
    ),
    tags=["breadth", "proxy"],
    calculation_function="tick_index",
)


_ADVANCE_DECLINE_PROXY = IndicatorMetadata(
    id="advance_decline_proxy",
    name="Advance/Decline Proxy",
    category="Breadth",
    description=(
        "Net intra-bar direction (close vs open) summed over "
        "trailing window. Range [-period, +period]. Distinct from "
        "tick_index (which uses close-to-close)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "A/D Proxy = bullish vs bearish bars net count. Window "
        "mein direction dominate kaun kar raha hai - bulls ya bears."
    ),
    tags=["breadth", "proxy"],
    calculation_function="advance_decline_proxy",
)


_MCCLELLAN_OSCILLATOR_PROXY = IndicatorMetadata(
    id="mcclellan_oscillator_proxy",
    name="McClellan Oscillator (proxy)",
    category="Breadth",
    description=(
        "Single-symbol McClellan: EMA(19) - EMA(39) of bar-direction "
        "stream. Centred near zero; positive = net buying momentum."
    ),
    inputs=[
        InputSpec(name="fast", type=InputType.NUMBER, default=19, min=2, max=200),
        InputSpec(name="slow", type=InputType.NUMBER, default=39, min=3, max=400),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "McClellan Proxy single-symbol breadth momentum. Positive "
        "+ rising = healthy uptrend; divergence with price = "
        "trend exhaustion warning."
    ),
    tags=["breadth", "proxy", "mcclellan"],
    calculation_function="mcclellan_oscillator_proxy",
)


_TRIN_PROXY = IndicatorMetadata(
    id="trin_proxy",
    name="TRIN / Arms Index (proxy)",
    category="Breadth",
    description=(
        "Single-symbol Arms Index: (bull_count / bear_count) / "
        "(bull_vol / bear_vol) over trailing window. > 1 = "
        "bearish (more vol on declines); < 1 = bullish."
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
        "TRIN Proxy = volume-weighted breadth ratio. >1 = "
        "selling pressure (bearish), <1 = buying (bullish). "
        "Counterintuitive: low TRIN = healthy market."
    ),
    tags=["breadth", "proxy", "arms"],
    calculation_function="trin_proxy",
)


# --- Cross-Asset Signals (4) ----------------------------------------


_RELATIVE_STRENGTH_VS_BENCHMARK = IndicatorMetadata(
    id="relative_strength_vs_benchmark",
    name="Relative Strength vs Benchmark (stub)",
    category="Cross-Asset",
    description=(
        "Rolling return of close vs a benchmark (NIFTY, etc.). "
        "**Phase 1 STUB** - returns all-None until the data-"
        "provider exposes a benchmark-series fetch (Phase 2). "
        "Same shape as nifty_correlation."
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
        "Relative Strength vs Benchmark stock vs NIFTY ka "
        "performance ratio. Phase 1 mein abhi stub hai (data-"
        "provider wiring Phase 2 mein) - None series milega tab tak."
    ),
    tags=["cross-asset", "stub"],
    calculation_function="relative_strength_vs_benchmark",
)


_CORRELATION_WITH_VOLUME = IndicatorMetadata(
    id="correlation_with_volume",
    name="Correlation with Volume",
    category="Cross-Asset",
    description=(
        "Rolling Pearson correlation of close vs volume. Range "
        "[-1, +1]. Sustained > +0.6 = healthy trending; < -0.6 = "
        "divergent."
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
        "Correlation with Volume = price + volume kitne sync mein "
        "hain. Strong positive = trend with conviction; negative "
        "= divergence (potential reversal)."
    ),
    tags=["cross-asset", "correlation"],
    calculation_function="correlation_with_volume",
)


_DIVERGENCE_STRENGTH_SCORE = IndicatorMetadata(
    id="divergence_strength_score",
    name="Divergence Strength Score",
    category="Divergence",
    description=(
        "Composite of Pack 11's RSI + MACD + OBV divergence "
        "codes. Range [-3, +3]. +3 = all three flagging bullish; "
        "-3 = all three flagging bearish (highest conviction)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Divergence Strength Score = 3 divergences (RSI / MACD / "
        "OBV) ka composite. +3 / -3 = highest-conviction reversal "
        "signal (sab agree kar rahe hain)."
    ),
    tags=["divergence", "composite"],
    calculation_function="divergence_strength_score",
)


_TREND_CONSISTENCY_SCORE = IndicatorMetadata(
    id="trend_consistency_score",
    name="Trend Consistency Score",
    category="Trend",
    description=(
        "Fraction of supplied SMA periods (default 10/20/50) "
        "whose slope agrees with the bar-to-bar short-term "
        "direction. Range [0, 1]. Continuous relative of "
        "Pack 8's ternary ``mtf_ema_alignment``."
    ),
    inputs=[
        InputSpec(
            name="timeframes", type=InputType.STRING, default="10,20,50",
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Trend Consistency Score = short-term direction se kitne "
        "SMA periods agree karte hain. 1.0 = strong trend (sab "
        "agree), 0.0 = reversal in progress."
    ),
    tags=["trend", "mtf"],
    calculation_function="trend_consistency_score",
)


# --- Aggregate -------------------------------------------------------


PACK13_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _FEAR_GREED_INDEX,
    _BREADTH_THRUST,
    _SENTIMENT_OSCILLATOR,
    _CAPITULATION_SIGNAL,
    _TICK_INDEX,
    _ADVANCE_DECLINE_PROXY,
    _MCCLELLAN_OSCILLATOR_PROXY,
    _TRIN_PROXY,
    _RELATIVE_STRENGTH_VS_BENCHMARK,
    _CORRELATION_WITH_VOLUME,
    _DIVERGENCE_STRENGTH_SCORE,
    _TREND_CONSISTENCY_SCORE,
)


__all__ = ["PACK13_ACTIVE_INDICATORS"]
