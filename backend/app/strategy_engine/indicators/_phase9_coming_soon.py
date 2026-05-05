"""Phase 9 — coming-soon indicator metadata stubs (no calculations).

These rows surface in the registry / builder UI as "coming soon" entries
so users can plan strategies that reference them. They have
``status = COMING_SOON`` and ``calculation_function = None``;
:func:`app.strategy_engine.indicators.registry.get_calculation_function`
raises on lookup, so the strategy execution path cannot accidentally
pick them up.

Each stub is built via the local :func:`_cs` helper to keep the data
table compact. The helper just calls :class:`IndicatorMetadata` with
the right defaults; it is not exported.
"""

from __future__ import annotations

from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
)


def _cs(
    *,
    indicator_id: str,
    name: str,
    category: str,
    description: str,
    ai_explanation: str,
    chart_type: IndicatorChartType = IndicatorChartType.SEPARATE,
    difficulty: IndicatorDifficulty = IndicatorDifficulty.INTERMEDIATE,
    tags: tuple[str, ...] = (),
) -> IndicatorMetadata:
    """Tight builder for a coming-soon row."""
    return IndicatorMetadata(
        id=indicator_id,
        name=name,
        category=category,
        description=description,
        inputs=[],
        outputs=[],
        chart_type=chart_type,
        pine_aliases=[],
        difficulty=difficulty,
        status=IndicatorStatus.COMING_SOON,
        ai_explanation=ai_explanation,
        tags=list(tags),
        calculation_function=None,
    )


# ─── Trend variants — moving averages and regression lines ─────────────


_TREND_STUBS: tuple[IndicatorMetadata, ...] = (
    _cs(
        indicator_id="dema",
        name="DEMA",
        category="Trend",
        description=(
            "Double Exponential Moving Average — 2*EMA - EMA(EMA), reduces "
            "lag relative to a single EMA without amplifying noise."
        ),
        ai_explanation=(
            "Use DEMA when you want EMA smoothing with snappier response "
            "to trend changes."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "moving-average"),
    ),
    _cs(
        indicator_id="tema",
        name="TEMA",
        category="Trend",
        description=(
            "Triple Exponential Moving Average — 3*EMA - 3*EMA(EMA) + "
            "EMA(EMA(EMA)). Even less lag than DEMA at the cost of more "
            "warm-up bars."
        ),
        ai_explanation="A faster trend line for traders who find EMA too slow.",
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "moving-average"),
    ),
    _cs(
        indicator_id="hull_ma",
        name="Hull MA",
        category="Trend",
        description=(
            "Hull Moving Average — weighted MA blend that minimises lag "
            "while keeping the line smooth."
        ),
        ai_explanation=(
            "HMA flips direction quickly on real trend changes; useful "
            "as a fast trend filter."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "moving-average"),
    ),
    _cs(
        indicator_id="kama",
        name="KAMA",
        category="Trend",
        description=(
            "Kaufman Adaptive Moving Average — adjusts smoothing based on "
            "an efficiency ratio so the line slows in chop and accelerates "
            "in trend."
        ),
        ai_explanation=(
            "KAMA reduces whipsaws in sideways markets while still "
            "tracking strong trends."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "adaptive"),
    ),
    _cs(
        indicator_id="alma",
        name="ALMA",
        category="Trend",
        description=(
            "Arnaud Legoux Moving Average — Gaussian-weighted smoothing "
            "with adjustable phase and sigma."
        ),
        ai_explanation=(
            "ALMA gives a smoother line than EMA at the same period; "
            "tune `offset` and `sigma` to taste."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "moving-average"),
    ),
    _cs(
        indicator_id="zlema",
        name="ZLEMA",
        category="Trend",
        description=(
            "Zero-Lag EMA (Ehlers) — EMA applied to a de-lagged input "
            "series so the output approximates the underlying without "
            "the EMA's intrinsic lag."
        ),
        ai_explanation="ZLEMA is the obvious upgrade when EMA's lag costs you trades.",
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "ehlers"),
    ),
    _cs(
        indicator_id="t3",
        name="T3 MA",
        category="Trend",
        description=(
            "Tillson T3 — six-stage smoothed MA with a volume factor, "
            "designed to be smoother and less laggy than DEMA."
        ),
        ai_explanation=(
            "T3 is heavy machinery for trend traders who care about a "
            "clean, low-lag line."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "moving-average"),
    ),
    _cs(
        indicator_id="frama",
        name="FRAMA",
        category="Trend",
        description=(
            "Fractal Adaptive Moving Average (Ehlers) — adapts smoothing "
            "based on the fractal dimension of price."
        ),
        ai_explanation=(
            "FRAMA tightens up in chop and loosens in trend — useful "
            "where regime varies a lot."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "ehlers", "adaptive"),
    ),
    _cs(
        indicator_id="mcginley",
        name="McGinley Dynamic",
        category="Trend",
        description=(
            "McGinley Dynamic — auto-adjusts speed when market gaps so "
            "the line tracks but does not overshoot."
        ),
        ai_explanation=(
            "Useful when volatility regimes change abruptly — McGinley "
            "absorbs gaps better than EMA."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend",),
    ),
    _cs(
        indicator_id="vidya",
        name="VIDYA",
        category="Trend",
        description=(
            "Variable Index Dynamic Average — Chande's adaptive MA where "
            "smoothing depends on momentum (CMO)."
        ),
        ai_explanation="VIDYA speeds up in strong moves and slows in chop.",
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "adaptive", "chande"),
    ),
    _cs(
        indicator_id="smma",
        name="SMMA",
        category="Trend",
        description=(
            "Smoothed Moving Average — equivalent to RMA / Wilder's "
            "smoothing applied to price."
        ),
        ai_explanation="SMMA is RSI's underlying smoothing applied as a price MA.",
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "wilder"),
    ),
    _cs(
        indicator_id="jurik_ma",
        name="Jurik MA",
        category="Trend",
        description=(
            "Jurik Moving Average — proprietary low-lag, low-overshoot "
            "smoothing popular in algorithmic systems."
        ),
        ai_explanation=(
            "Jurik MA is the gold-standard smooth trend line for "
            "professional desks."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend",),
    ),
    _cs(
        indicator_id="mama",
        name="MAMA",
        category="Trend",
        description=(
            "MESA Adaptive Moving Average (Ehlers) — adjusts via the "
            "Hilbert transform to track the dominant cycle."
        ),
        ai_explanation=(
            "MAMA + FAMA crossover is one of Ehlers' clean trend-change "
            "signals."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("trend", "ehlers", "adaptive"),
    ),
    _cs(
        indicator_id="fama",
        name="FAMA",
        category="Trend",
        description=(
            "Following Adaptive Moving Average — companion line to MAMA, "
            "lags MAMA so crossovers signal trend changes."
        ),
        ai_explanation=(
            "FAMA is half the speed of MAMA and is paired with it for "
            "crossover entries."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("trend", "ehlers"),
    ),
    _cs(
        indicator_id="lsma_slope",
        name="LR Slope",
        category="Trend",
        description=(
            "Slope of the linear regression line over the trailing "
            "window. Positive means rising regression; negative means "
            "falling."
        ),
        ai_explanation=(
            "Use slope sign as a directional gate; magnitude as a "
            "trend-strength proxy."
        ),
        tags=("trend", "regression"),
    ),
    _cs(
        indicator_id="lsma_intercept",
        name="LR Intercept",
        category="Trend",
        description="Intercept of the OLS line at the start of the window.",
        ai_explanation="Mostly useful when wired into a custom regression metric.",
        tags=("trend", "regression"),
    ),
    _cs(
        indicator_id="lsma_angle",
        name="LR Angle",
        category="Trend",
        description=(
            "Angle of the linear regression line in degrees. Useful for "
            "comparing trend steepness across symbols of different price "
            "scales."
        ),
        ai_explanation=(
            "Angle above ~30° on the 14-bar regression typically marks "
            "a strong directional move."
        ),
        tags=("trend", "regression"),
    ),
    _cs(
        indicator_id="regression_channel",
        name="Regression Channel",
        category="Trend",
        description=(
            "Linear regression line with parallel +/- N standard-deviation "
            "bands forming a regression channel."
        ),
        ai_explanation=(
            "Tag of the upper band in an uptrend is mean-reverting; tag "
            "of the lower band can mark continuation entries."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("trend", "regression", "bands"),
    ),
)


# ─── Momentum / oscillators ────────────────────────────────────────────


_MOMENTUM_STUBS: tuple[IndicatorMetadata, ...] = (
    _cs(
        indicator_id="stochastic",
        name="Stochastic",
        category="Momentum",
        description=(
            "Stochastic %K and %D — oscillator that locates the close "
            "within the trailing high-low range. Range 0-100."
        ),
        ai_explanation=(
            "%K above 80 is overbought; below 20 oversold. %K crossing "
            "%D inside those zones is the classic Stochastic entry."
        ),
        difficulty=IndicatorDifficulty.BEGINNER,
        tags=("momentum", "oscillator", "beginner"),
    ),
    _cs(
        indicator_id="stoch_rsi",
        name="Stochastic RSI",
        category="Momentum",
        description=(
            "Stochastic of RSI — applies the stochastic transformation to "
            "the RSI series for finer-grained overbought / oversold reads."
        ),
        ai_explanation=(
            "More sensitive than vanilla RSI; useful for short timeframes "
            "where RSI itself rarely tags 30 / 70."
        ),
        tags=("momentum", "oscillator"),
    ),
    _cs(
        indicator_id="williams_r",
        name="Williams %R",
        category="Momentum",
        description=(
            "Williams %R — close relative to the trailing high-low range, "
            "scaled -100 to 0."
        ),
        ai_explanation=(
            "Above -20 overbought; below -80 oversold. Mirror image of "
            "Stochastic."
        ),
        tags=("momentum", "oscillator", "williams"),
    ),
    _cs(
        indicator_id="cci",
        name="CCI",
        category="Momentum",
        description=(
            "Commodity Channel Index — mean-deviation oscillator, "
            "typically scaled so +/-100 mark significant moves."
        ),
        ai_explanation=(
            "CCI > +100 indicates strong up-momentum; < -100 strong "
            "down-momentum. Useful in commodity-like markets."
        ),
        tags=("momentum", "oscillator", "lambert"),
    ),
    _cs(
        indicator_id="roc",
        name="ROC",
        category="Momentum",
        description=(
            "Rate of Change — close[i] - close[i - period]. Direct "
            "momentum measurement in price units."
        ),
        ai_explanation=(
            "Crosses of zero mark sign changes in the period-over-period "
            "trend."
        ),
        difficulty=IndicatorDifficulty.BEGINNER,
        tags=("momentum", "beginner"),
    ),
    _cs(
        indicator_id="roc_percent",
        name="ROC %",
        category="Momentum",
        description=(
            "Rate of Change as a percentage — (close - close[-period]) / "
            "close[-period] * 100."
        ),
        ai_explanation=(
            "Better than raw ROC for cross-symbol comparison since it "
            "normalises out price scale."
        ),
        tags=("momentum",),
    ),
    _cs(
        indicator_id="momentum",
        name="Momentum",
        category="Momentum",
        description="Raw momentum — close[i] / close[i - period].",
        ai_explanation="Above 1 is up-momentum; below 1 is down-momentum.",
        tags=("momentum",),
    ),
    _cs(
        indicator_id="awesome_oscillator",
        name="Awesome Oscillator",
        category="Momentum",
        description=(
            "Bill Williams' Awesome Oscillator — SMA(median, 5) - "
            "SMA(median, 34)."
        ),
        ai_explanation=(
            "Histogram colour change above zero is a momentum-up signal; "
            "below zero, momentum-down."
        ),
        tags=("momentum", "williams"),
    ),
    _cs(
        indicator_id="accelerator_oscillator",
        name="Accelerator Oscillator",
        category="Momentum",
        description=(
            "AO - SMA(AO, 5). Measures the second derivative of price — "
            "flags whether momentum itself is accelerating."
        ),
        ai_explanation=(
            "Two consecutive bars same colour above / below zero is the "
            "classic Accelerator entry."
        ),
        tags=("momentum", "williams"),
    ),
    _cs(
        indicator_id="ppo",
        name="PPO",
        category="Momentum",
        description=(
            "Percentage Price Oscillator — MACD expressed as a percentage "
            "of the slow EMA so it is comparable across price scales."
        ),
        ai_explanation="Use PPO instead of MACD when comparing across symbols.",
        tags=("momentum", "macd-family"),
    ),
    _cs(
        indicator_id="dpo",
        name="DPO",
        category="Momentum",
        description=(
            "Detrended Price Oscillator — price minus an SMA shifted "
            "back, isolating cyclical components."
        ),
        ai_explanation="DPO peaks / troughs map out the dominant short-term cycle.",
        tags=("momentum", "cycle"),
    ),
    _cs(
        indicator_id="balance_of_power",
        name="Balance of Power",
        category="Momentum",
        description=(
            "Balance of Power — (close - open) / (high - low). "
            "Per-bar tug-of-war between buyers and sellers."
        ),
        ai_explanation=(
            "Sustained BOP > 0 indicates buyers in control; < 0 sellers."
        ),
        tags=("momentum",),
    ),
    _cs(
        indicator_id="chande_momentum",
        name="Chande Momentum",
        category="Momentum",
        description=(
            "Chande Momentum Oscillator — sum-of-up-moves minus sum-of-"
            "down-moves, normalised. Range -100 to +100."
        ),
        ai_explanation="More responsive than RSI in fast-moving markets.",
        tags=("momentum", "chande"),
    ),
    _cs(
        indicator_id="fisher_transform",
        name="Fisher Transform",
        category="Momentum",
        description=(
            "Ehlers' Fisher Transform — applies a non-linear transform "
            "to bring price toward a Gaussian distribution, sharpening "
            "turning points."
        ),
        ai_explanation=(
            "Sharp peaks in the Fisher line are unusually clean reversal "
            "signals when paired with price action."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("momentum", "ehlers"),
    ),
    _cs(
        indicator_id="rmi",
        name="RMI",
        category="Momentum",
        description=(
            "Relative Momentum Index — RSI with a configurable lookback "
            "for the up / down move calculation."
        ),
        ai_explanation=(
            "RMI(2-3) is a popular short-cycle oversold filter used in "
            "Connors-style mean-reversion systems."
        ),
        tags=("momentum",),
    ),
    _cs(
        indicator_id="pmo",
        name="PMO",
        category="Momentum",
        description=(
            "Price Momentum Oscillator — DecisionPoint's smoothed ROC with "
            "a signal line."
        ),
        ai_explanation="Smoother than MACD; signal-line crossovers are slower but cleaner.",
        tags=("momentum",),
    ),
    _cs(
        indicator_id="ergodic_oscillator",
        name="Ergodic Oscillator",
        category="Momentum",
        description=(
            "Ergodic Oscillator (Blau) — double-smoothed price change as "
            "a percent of double-smoothed absolute price change."
        ),
        ai_explanation=(
            "Less prone to whipsaws than MACD; signal-line crossovers "
            "in trending markets are reliable entries."
        ),
        tags=("momentum",),
    ),
    _cs(
        indicator_id="klinger_oscillator",
        name="Klinger Oscillator",
        category="Volume",
        description=(
            "Klinger Volume Oscillator — long minus short EMAs of a "
            "volume-force series."
        ),
        ai_explanation=(
            "Use signal-line crossovers; divergence with price is the "
            "classic Klinger reversal cue."
        ),
        tags=("volume", "klinger"),
    ),
)


# ─── Volatility / bands / structure ────────────────────────────────────


_VOLATILITY_STUBS: tuple[IndicatorMetadata, ...] = (
    _cs(
        indicator_id="keltner_channel",
        name="Keltner Channel",
        category="Volatility",
        description=(
            "Keltner Channel — EMA of price with ATR-scaled bands above "
            "and below."
        ),
        ai_explanation=(
            "Tight Keltner channels mark low-volatility consolidation; "
            "breakouts often coincide with the Bollinger squeeze."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "bands"),
    ),
    _cs(
        indicator_id="donchian_channel",
        name="Donchian Channel",
        category="Volatility",
        description=(
            "Donchian Channel — highest high and lowest low over the "
            "trailing N bars; classic Turtles breakout system input."
        ),
        ai_explanation=(
            "20-bar Donchian breakouts are the canonical Turtles entry "
            "rule; 10-bar exits the Turtles trail."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "breakout"),
    ),
    _cs(
        indicator_id="parabolic_sar",
        name="Parabolic SAR",
        category="Volatility",
        description=(
            "Wilder's Parabolic SAR — flips above / below price as the "
            "trail-stop accelerates."
        ),
        ai_explanation=(
            "Use SAR as a stop-and-reverse trail; works best in "
            "trending regimes, fails in chop."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "wilder", "trail-stop"),
    ),
    _cs(
        indicator_id="supertrend",
        name="SuperTrend",
        category="Volatility",
        description=(
            "SuperTrend — ATR-scaled trail line that flips colour when "
            "price closes through it."
        ),
        ai_explanation=(
            "SuperTrend flips are popular pyramid-trail rules; sensitive "
            "to ATR multiplier choice."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "trail"),
    ),
    _cs(
        indicator_id="atr_bands",
        name="ATR Bands",
        category="Volatility",
        description=(
            "Price +/- N x ATR forming volatility-scaled bands — used "
            "for ATR-based stops and Chandelier-style trails."
        ),
        ai_explanation=(
            "Set stops at N x ATR from entry to size risk consistently "
            "across symbols."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "atr"),
    ),
    _cs(
        indicator_id="std_dev",
        name="Standard Deviation",
        category="Volatility",
        description="Rolling standard deviation of the source series.",
        ai_explanation=(
            "Direct volatility measure; building block for Bollinger "
            "Bands and many bands-and-channels indicators."
        ),
        tags=("volatility",),
    ),
    _cs(
        indicator_id="historical_volatility",
        name="Historical Volatility",
        category="Volatility",
        description=(
            "Annualised standard deviation of log returns over the "
            "trailing window."
        ),
        ai_explanation=(
            "HV is the realised-vol benchmark options traders compare "
            "against implied vol."
        ),
        tags=("volatility",),
    ),
    _cs(
        indicator_id="ulcer_index",
        name="Ulcer Index",
        category="Volatility",
        description=(
            "Peter Martin's Ulcer Index — RMS of percent drawdowns over "
            "the trailing window. Penalises depth AND duration."
        ),
        ai_explanation="Lower Ulcer is better; useful for risk-adjusted comparisons.",
        tags=("volatility", "drawdown"),
    ),
    _cs(
        indicator_id="volatility_ratio",
        name="Volatility Ratio",
        category="Volatility",
        description=(
            "Short-period volatility divided by long-period volatility — "
            "expansion vs contraction signal."
        ),
        ai_explanation=(
            "Ratio > 1 indicates volatility expansion (often precedes "
            "trend); < 1 indicates contraction."
        ),
        tags=("volatility",),
    ),
    _cs(
        indicator_id="envelopes",
        name="Envelopes",
        category="Volatility",
        description=(
            "Moving-average +/- fixed-percentage bands — simpler "
            "ancestor of Bollinger / Keltner."
        ),
        ai_explanation=(
            "Tight envelopes are useful as overbought / oversold "
            "guides on slow-moving instruments."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "bands"),
    ),
    _cs(
        indicator_id="percentile_bands",
        name="Percentile Bands",
        category="Volatility",
        description=(
            "Upper / lower bands at the Nth and (100-N)th percentile of "
            "the trailing distribution."
        ),
        ai_explanation="Robust alternative to standard-deviation bands when returns are non-normal.",
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "bands"),
    ),
    _cs(
        indicator_id="std_error_bands",
        name="Standard Error Bands",
        category="Volatility",
        description=(
            "Linear regression line with bands at +/- N standard errors "
            "of the regression."
        ),
        ai_explanation=(
            "Bands scale with regression fit quality — wider in sloppy "
            "tape, tighter when the trend is well-defined."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "regression", "bands"),
    ),
    _cs(
        indicator_id="fractal_chaos_bands",
        name="Fractal Chaos Bands",
        category="Volatility",
        description=(
            "Bands drawn at the most recent up / down fractals so they "
            "step rather than slide."
        ),
        ai_explanation=(
            "Useful as breakout level candidates that update only on "
            "structural pivots."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volatility", "fractal"),
    ),
    _cs(
        indicator_id="ttm_squeeze",
        name="TTM Squeeze",
        category="Volatility",
        description=(
            "John Carter's TTM Squeeze — Bollinger inside Keltner "
            "indicates a volatility squeeze about to fire."
        ),
        ai_explanation=(
            "Squeeze ON + momentum confirmation flip is the canonical "
            "Carter entry."
        ),
        tags=("volatility", "squeeze", "breakout"),
    ),
    _cs(
        indicator_id="choppiness_index",
        name="Choppiness Index",
        category="Volatility",
        description=(
            "Choppiness Index — measures whether the market is trending "
            "or chopping on a 0-100 scale."
        ),
        ai_explanation=(
            "Above 61.8 = chop (avoid trend systems); below 38.2 = "
            "trend (avoid mean-reversion)."
        ),
        tags=("volatility", "regime"),
    ),
    _cs(
        indicator_id="vortex",
        name="Vortex",
        category="Trend",
        description=(
            "Vortex Indicator — paired VI+ and VI- lines that cross to "
            "signal trend changes."
        ),
        ai_explanation=(
            "VI+ crossing above VI- is bullish; the inverse is bearish. "
            "Pair with ADX for filtering."
        ),
        tags=("trend",),
    ),
    _cs(
        indicator_id="mass_index",
        name="Mass Index",
        category="Volatility",
        description=(
            "Donald Dorsey's Mass Index — sum of high-low ratios used to "
            "predict reversals via the 'reversal bulge'."
        ),
        ai_explanation=(
            "A bulge above 27 followed by a drop below 26.5 is the "
            "classic Dorsey reversal trigger."
        ),
        tags=("volatility", "reversal"),
    ),
)


# ─── Volume ────────────────────────────────────────────────────────────


_VOLUME_STUBS: tuple[IndicatorMetadata, ...] = (
    _cs(
        indicator_id="adl",
        name="Accumulation/Distribution Line",
        category="Volume",
        description=(
            "Chaikin's running A/D Line — cumulative money-flow volume."
        ),
        ai_explanation=(
            "ADL trending up while price chops sideways suggests "
            "accumulation; the reverse signals distribution."
        ),
        tags=("volume", "chaikin"),
    ),
    _cs(
        indicator_id="mfi",
        name="MFI",
        category="Volume",
        description=(
            "Money Flow Index — RSI with volume weighting; range 0-100."
        ),
        ai_explanation=(
            "Volume-aware overbought / oversold filter; less prone to "
            "low-conviction extremes than RSI."
        ),
        tags=("volume", "momentum"),
    ),
    _cs(
        indicator_id="eom",
        name="Ease of Movement",
        category="Volume",
        description=(
            "Arms' Ease of Movement — relates price change to volume "
            "and range; high values mean small volume drove a big move."
        ),
        ai_explanation=(
            "Sustained positive EOM indicates effortless rallies; "
            "negative EOM means selling needs little volume."
        ),
        tags=("volume",),
    ),
    _cs(
        indicator_id="nvi",
        name="Negative Volume Index",
        category="Volume",
        description=(
            "Negative Volume Index — accumulates returns only on "
            "low-volume bars (smart money proxy)."
        ),
        ai_explanation=(
            "NVI tracking up indicates smart money is buying on quiet "
            "bars; classic pair-trade signal with PVI."
        ),
        tags=("volume",),
    ),
    _cs(
        indicator_id="pvi",
        name="Positive Volume Index",
        category="Volume",
        description=(
            "Positive Volume Index — accumulates returns only on "
            "high-volume bars (crowd proxy)."
        ),
        ai_explanation="Pairs with NVI; divergences flag smart-vs-crowd disagreement.",
        tags=("volume",),
    ),
    _cs(
        indicator_id="kvo",
        name="KVO",
        category="Volume",
        description=(
            "Klinger Volume Oscillator — long-period MA of force volume "
            "minus short-period MA."
        ),
        ai_explanation=(
            "Use KVO signal-line crossovers and divergence with price for "
            "reversals."
        ),
        tags=("volume", "klinger"),
    ),
    _cs(
        indicator_id="vpt",
        name="VPT",
        category="Volume",
        description=(
            "Volume Price Trend — running sum of percent price change "
            "weighted by volume."
        ),
        ai_explanation="Cleaner alternative to OBV; sign tracks the dominant flow.",
        tags=("volume",),
    ),
    _cs(
        indicator_id="vwma",
        name="VWMA",
        category="Volume",
        description=(
            "Volume-Weighted Moving Average — SMA where each bar's "
            "weight is its volume."
        ),
        ai_explanation=(
            "VWMA leads SMA when volume confirms moves; useful overlay "
            "next to a vanilla MA."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("volume", "moving-average"),
    ),
    _cs(
        indicator_id="twiggs_money_flow",
        name="Twiggs Money Flow",
        category="Volume",
        description=(
            "Colin Twiggs' refined CMF that uses true range to fix CMF's "
            "behaviour around gaps."
        ),
        ai_explanation="Drop-in CMF replacement for instruments that gap regularly.",
        tags=("volume", "twiggs"),
    ),
    _cs(
        indicator_id="demand_index",
        name="Demand Index",
        category="Volume",
        description=(
            "James Sibbet's Demand Index — combines price and volume to "
            "measure demand pressure."
        ),
        ai_explanation=(
            "Demand divergence with price is one of the older but still "
            "respected reversal signals."
        ),
        tags=("volume",),
    ),
    _cs(
        indicator_id="vix_fix",
        name="VIX Fix",
        category="Volatility",
        description=(
            "Larry Williams' VIX Fix — synthetic implied-volatility "
            "proxy computable from price alone."
        ),
        ai_explanation=(
            "Spikes in VIX Fix mark capitulation lows in equity-like "
            "instruments."
        ),
        tags=("volatility", "williams"),
    ),
)


# ─── Patterns / structure / fibonacci / pivots ─────────────────────────


_PATTERN_AND_PIVOT_STUBS: tuple[IndicatorMetadata, ...] = (
    _cs(
        indicator_id="heikin_ashi",
        name="Heikin Ashi",
        category="Pattern",
        description=(
            "Heikin Ashi — averaged candles that smooth out the trend "
            "by averaging open, high, low, and close."
        ),
        ai_explanation=(
            "Pure-colour HA candle runs are clean trend signals at the "
            "cost of obscuring the true open / close."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        difficulty=IndicatorDifficulty.BEGINNER,
        tags=("pattern", "smoothed", "beginner"),
    ),
    _cs(
        indicator_id="renko",
        name="Renko",
        category="Pattern",
        description=(
            "Renko bricks — price-only chart where new bricks print "
            "after a fixed move, ignoring time."
        ),
        ai_explanation=(
            "Renko strips out time; clean for trend systems but loses "
            "entry-bar timing detail."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("pattern", "price-only"),
    ),
    _cs(
        indicator_id="range_bars",
        name="Range Bars",
        category="Pattern",
        description=(
            "Range bars — fixed-range candles, similar in spirit to "
            "Renko but with wicks."
        ),
        ai_explanation=(
            "Range bars normalise volatility — every bar represents "
            "the same price travel."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("pattern", "price-only"),
    ),
    _cs(
        indicator_id="zigzag",
        name="ZigZag",
        category="Pattern",
        description=(
            "ZigZag overlay — connects significant pivots; filters out "
            "moves smaller than a threshold."
        ),
        ai_explanation=(
            "Useful as a structure cleanup tool, not a signal — the "
            "current leg can repaint until confirmed."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("pattern", "structure"),
    ),
    _cs(
        indicator_id="fractals",
        name="Fractals",
        category="Pattern",
        description=(
            "Bill Williams' Fractals — five-bar pivot pattern marking "
            "swing highs and lows."
        ),
        ai_explanation=(
            "Used as structural support / resistance; up-fractal is a "
            "swing high, down-fractal a swing low."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("pattern", "williams", "structure"),
    ),
    _cs(
        indicator_id="market_facilitation_index",
        name="Market Facilitation Index",
        category="Volume",
        description=(
            "Bill Williams' MFI — bar range divided by volume; combined "
            "with volume change to classify bar types."
        ),
        ai_explanation=(
            "Green / fade / fake / squat tiles describe how easily price "
            "moved given the volume."
        ),
        tags=("volume", "williams"),
    ),
    _cs(
        indicator_id="fib_retracement",
        name="Fibonacci Retracement",
        category="Support/Resistance",
        description=(
            "Fibonacci retracement levels (0.236, 0.382, 0.5, 0.618, "
            "0.786) drawn between two anchored pivots."
        ),
        ai_explanation=(
            "Common pullback magnets in trending markets; 0.618 is the "
            "most-watched."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("support-resistance", "fibonacci"),
    ),
    _cs(
        indicator_id="fib_extension",
        name="Fibonacci Extension",
        category="Support/Resistance",
        description=(
            "Extensions beyond 100 % (1.272, 1.414, 1.618, 2.0) used as "
            "profit-taking targets."
        ),
        ai_explanation=(
            "1.618 extension is the canonical Fibonacci take-profit "
            "ladder anchor."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("support-resistance", "fibonacci"),
    ),
    _cs(
        indicator_id="fib_fan",
        name="Fibonacci Fan",
        category="Support/Resistance",
        description=(
            "Fibonacci-angled trend lines emanating from a pivot — "
            "diagonal support / resistance candidates."
        ),
        ai_explanation=(
            "Useful when price respects diagonals more than horizontal "
            "levels."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("support-resistance", "fibonacci"),
    ),
    _cs(
        indicator_id="fib_time_zones",
        name="Fibonacci Time Zones",
        category="Support/Resistance",
        description=(
            "Vertical lines at Fibonacci-spaced bar counts from an "
            "anchor — projects time-symmetry pivots."
        ),
        ai_explanation=(
            "More astrology than science, but common in some discretionary "
            "playbooks."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("support-resistance", "fibonacci"),
    ),
    _cs(
        indicator_id="camarilla_pivots",
        name="Camarilla Pivots",
        category="Support/Resistance",
        description=(
            "Camarilla pivot levels — alternative pivot formulas with "
            "tighter intraday levels."
        ),
        ai_explanation=(
            "L3 / H3 levels are the popular intraday breakout / "
            "breakdown triggers."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("support-resistance", "pivot", "intraday"),
    ),
    _cs(
        indicator_id="woodie_pivots",
        name="Woodie Pivots",
        category="Support/Resistance",
        description=(
            "Woodie pivot levels — variant that weights the close more "
            "heavily than the standard formula."
        ),
        ai_explanation=(
            "Tends to align with intraday consolidation midpoints "
            "better than classic pivots."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("support-resistance", "pivot"),
    ),
    _cs(
        indicator_id="demark_pivots",
        name="DeMark Pivots",
        category="Support/Resistance",
        description=(
            "Tom DeMark's pivot variant — formula switches based on the "
            "close vs open relationship of the prior bar."
        ),
        ai_explanation=(
            "DeMark levels are gentler than classic pivots; useful in "
            "low-volatility regimes."
        ),
        chart_type=IndicatorChartType.OVERLAY,
        tags=("support-resistance", "pivot", "demark"),
    ),
)


# ─── Cycles / sentiment / breadth ──────────────────────────────────────


_CYCLES_AND_BREADTH_STUBS: tuple[IndicatorMetadata, ...] = (
    _cs(
        indicator_id="hilbert_transform",
        name="Hilbert Transform",
        category="Cycle",
        description=(
            "Ehlers' Hilbert Transform — analytic signal extraction used "
            "as a building block for adaptive cycle indicators."
        ),
        ai_explanation=(
            "Mostly used internally — Hilbert powers MAMA, dominant-cycle "
            "estimation, and similar adaptive systems."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("cycle", "ehlers"),
    ),
    _cs(
        indicator_id="dominant_cycle",
        name="Dominant Cycle Period",
        category="Cycle",
        description=(
            "Estimated dominant cycle period (in bars) using Hilbert "
            "transform decomposition."
        ),
        ai_explanation=(
            "Feed into adaptive indicator periods so they auto-tune to "
            "the current rhythm."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("cycle", "ehlers", "adaptive"),
    ),
    _cs(
        indicator_id="sine_wave",
        name="Ehlers Sine Wave",
        category="Cycle",
        description=(
            "Ehlers' Sine Wave indicator — dominant cycle expressed as "
            "a sine and a leading sine."
        ),
        ai_explanation=(
            "Crossings of the two sine waves provide low-lag turning "
            "points in cyclic markets."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("cycle", "ehlers"),
    ),
    _cs(
        indicator_id="mesa_sine",
        name="MESA Sine Wave",
        category="Cycle",
        description=(
            "MESA-derived sine pair from the Hilbert transform; cleaner "
            "in transitionary regimes than the basic sine wave."
        ),
        ai_explanation=(
            "Use when basic sine wave whipsaws on regime transitions."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("cycle", "mesa", "ehlers"),
    ),
    _cs(
        indicator_id="schaff_trend_cycle",
        name="Schaff Trend Cycle",
        category="Momentum",
        description=(
            "Doug Schaff's STC — stochastic of MACD with extra smoothing; "
            "fast oscillator that reacts quickly to trend changes."
        ),
        ai_explanation=(
            "Cross of 75 from above is a sell; cross of 25 from below "
            "is a buy."
        ),
        tags=("momentum", "macd-family", "stochastic"),
    ),
    _cs(
        indicator_id="ehlers_fisher",
        name="Ehlers Fisher",
        category="Momentum",
        description=(
            "Ehlers-style Fisher transformation paired with a trigger "
            "line one bar back."
        ),
        ai_explanation=(
            "Trigger crossing the Fisher line is the classic Ehlers "
            "entry / exit cue."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("momentum", "ehlers"),
    ),
    _cs(
        indicator_id="arms_index_trin",
        name="Arms Index (TRIN)",
        category="Breadth",
        description=(
            "Richard Arms' market-breadth indicator — advancing/declining "
            "issues divided by advancing/declining volume."
        ),
        ai_explanation=(
            "TRIN > 1 indicates net selling pressure across the market; "
            "< 1 net buying."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("breadth", "market-internals"),
    ),
    _cs(
        indicator_id="mcclellan_oscillator",
        name="McClellan Oscillator",
        category="Breadth",
        description=(
            "McClellan Oscillator — difference between two EMAs of net "
            "advances/declines."
        ),
        ai_explanation=(
            "Crosses of the zero line track market-breadth-driven "
            "regime changes."
        ),
        difficulty=IndicatorDifficulty.EXPERT,
        tags=("breadth", "market-internals"),
    ),
)


PHASE9_COMING_SOON_INDICATORS: tuple[IndicatorMetadata, ...] = (
    *_TREND_STUBS,
    *_MOMENTUM_STUBS,
    *_VOLATILITY_STUBS,
    *_VOLUME_STUBS,
    *_PATTERN_AND_PIVOT_STUBS,
    *_CYCLES_AND_BREADTH_STUBS,
)


__all__ = ["PHASE9_COMING_SOON_INDICATORS"]
