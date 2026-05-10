"""Pack 18 - 15 final indicators. MILESTONE PACK: hits 230 active.

The closing pack of the indicator-build campaign. 14 net-new
indicators + 1 promotion-from-coming_soon (``ttm_squeeze``). The
promotion uses the established Pack 4 pattern (splat after
``*PHASE9_COMING_SOON_INDICATORS`` overrides the same-id stub) -
no modification to ``_phase9_coming_soon.py`` itself.

Two honest stubs (Pack 8 / 13 / 16 lesson):

    * ``nse_bse_arbitrage_proxy`` - needs parallel NSE+BSE feed.
      ``HAS_DUAL_EXCHANGE = False``; returns all-None.
    * ``nifty_50_relative_position`` - needs symbol-to-NIFTY-
      component mapping + NIFTY candles. ``HAS_SYMBOL_CONTEXT =
      False``; returns all-None.

One Pine alias added: ``ta.mom`` -> ``momentum_oscillator``
(documented in pine_import/parser.py SUPPORTED_TA_INDICATORS and
mapper.py). The other 14 indicators have no Pine v5 ta.* match.
Lock test ``test_pack18_only_documented_pine_aliases`` pins the
contract.

Distinguishing notes:

    * ``momentum_oscillator`` - raw ``close - close[period]`` (Pine
      ta.mom). Distinct from ROC (percent) and from Pack 17's
      ``momentum_quality_score`` (0..100 composite).
    * ``price_momentum_index`` - LWMA-stretch percent. Distinct from
      momentum_oscillator (price units) and trend_momentum_combo
      (ATR-normalised, signed by trend).
    * ``positive_volume_index_signal`` - EMA of Pack 10 PVI.
      Distinct from PVI itself (the index); the signal line is the
      smoothed reference for crossover signals (Fosback's "Smart
      Money / Dumb Money" framework).

Difficulty split (BEGINNER / INTERMEDIATE / EXPERT):

    INTERMEDIATE (4) - ttm_squeeze, momentum_oscillator,
                       roc_smoothed, fno_lot_size_atr
    EXPERT (11)      - everything else (composites, multi-stage
                       signals, F&O context, both stubs)
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

# --- Trend Completers (5) ------------------------------------------


_TTM_SQUEEZE = IndicatorMetadata(
    id="ttm_squeeze",
    name="TTM Squeeze",
    category="Volatility",
    description=(
        "John Carter's TTM Squeeze. 1.0 when Bollinger inside "
        "Keltner (squeeze ON, volatility coiled), 0.0 otherwise. "
        "Promoted from Phase 9 coming-soon stub."
    ),
    inputs=[
        InputSpec(name="bb_period", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(name="kc_period", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(name="bb_std", type=InputType.NUMBER, default=2.0, min=0.1, max=10.0),
        InputSpec(name="kc_mult", type=InputType.NUMBER, default=1.5, min=0.1, max=10.0),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "TTM Squeeze = BB Keltner ke andar hai? Squeeze ON (1.0) "
        "= volatility coil ho rahi hai, breakout aane wala. Carter "
        "ka classic setup."
    ),
    tags=["volatility", "squeeze", "carter"],
    calculation_function="ttm_squeeze",
)


_TTM_SQUEEZE_PRO = IndicatorMetadata(
    id="ttm_squeeze_pro",
    name="TTM Squeeze Pro",
    category="Volatility",
    description=(
        "4-level squeeze tightness (0=off, 1=loose, 2=normal, "
        "3=tight) using two Keltner widths. Tighter = bigger "
        "expected pop on release."
    ),
    inputs=[
        InputSpec(name="bb_period", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(name="kc_period", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(
            name="low_volatility_mult", type=InputType.NUMBER,
            default=1.0, min=0.1, max=10.0,
        ),
        InputSpec(
            name="high_volatility_mult", type=InputType.NUMBER,
            default=2.0, min=0.2, max=20.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "TTM Squeeze Pro = squeeze level 0..3. 3 = tightest (bada "
        "expected move), 0 = no squeeze. Carter ka extension."
    ),
    tags=["volatility", "squeeze", "carter", "graded"],
    calculation_function="ttm_squeeze_pro",
)


_WEEKLY_TREND_STRENGTH = IndicatorMetadata(
    id="weekly_trend_strength",
    name="Weekly Trend Strength",
    category="Trend",
    description=(
        "0..100 % of last `weeks` weekly-blocks (5 bars each) that "
        "closed in the same direction as the current week. Bar-"
        "based proxy; daily candles work directly, intraday users "
        "should resample."
    ),
    inputs=[
        InputSpec(name="weeks", type=InputType.NUMBER, default=4, min=2, max=52),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Weekly Trend Strength = pichle hafton mein same direction "
        "kitne the. >75 = strong multi-week trend."
    ),
    tags=["trend", "weekly"],
    calculation_function="weekly_trend_strength",
)


_TREND_AGE_BARS = IndicatorMetadata(
    id="trend_age_bars",
    name="Trend Age (Bars Since EMA Cross)",
    category="Trend",
    description=(
        "Bars since the last EMA-fast / EMA-slow cross. Resets to "
        "0 at each cross. Useful as a trend-exhaustion filter - "
        "very old trends carry more reversion risk."
    ),
    inputs=[
        InputSpec(name="ema_fast", type=InputType.NUMBER, default=12, min=1, max=200),
        InputSpec(name="ema_slow", type=InputType.NUMBER, default=26, min=2, max=400),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Trend Age = last EMA cross ke baad kitne bars. Lambi "
        "trends mein reversion risk badh jata hai."
    ),
    tags=["trend", "age"],
    calculation_function="trend_age_bars",
)


_CONSECUTIVE_HIGHER_LOWS = IndicatorMetadata(
    id="consecutive_higher_lows",
    name="Consecutive Higher Lows",
    category="Pattern",
    description=(
        "Running count of consecutive bars where low > prior low, "
        "capped at `lookback`. Resets to 0 on any HL break. "
        "Structural-uptrend detector."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=10, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Consecutive Higher Lows = continuous HL count. Structural "
        "uptrend tracker, kisi bhi HL break par 0."
    ),
    tags=["pattern", "structure"],
    calculation_function="consecutive_higher_lows",
)


# --- Momentum Completers (4) --------------------------------------


_ROC_SMOOTHED = IndicatorMetadata(
    id="roc_smoothed",
    name="Smoothed ROC",
    category="Momentum",
    description=(
        "EMA-smoothed Rate of Change. Reduces ROC's whipsaw by "
        "applying an EMA over the raw ROC line."
    ),
    inputs=[
        InputSpec(name="roc_period", type=InputType.NUMBER, default=10, min=1, max=200),
        InputSpec(name="smooth_period", type=InputType.NUMBER, default=5, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Smoothed ROC = EMA of ROC. Whipsaw kam karta hai, signal "
        "stable hota hai."
    ),
    tags=["momentum", "roc"],
    calculation_function="roc_smoothed",
)


_MOMENTUM_OSCILLATOR = IndicatorMetadata(
    id="momentum_oscillator",
    name="Momentum Oscillator",
    category="Momentum",
    description=(
        "Classic momentum: close[i] - close[i-period]. Pine "
        "ta.mom equivalent. Distinct from ROC (percent) and "
        "Pack 17 momentum_quality_score (composite)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=10, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=["ta.mom"],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Momentum Oscillator = close - close[period]. Sign + "
        "magnitude in price units. Pine ta.mom ka same."
    ),
    tags=["momentum", "classic"],
    calculation_function="momentum_oscillator",
)


_PRICE_MOMENTUM_INDEX = IndicatorMetadata(
    id="price_momentum_index",
    name="Price Momentum Index (PMI)",
    category="Momentum",
    description=(
        "(close - LWMA) / LWMA * 100. LWMA weights recent bars "
        "more. Distinct from momentum_oscillator (price units) "
        "and trend_momentum_combo (ATR-normalised, trend-signed)."
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
        "PMI = LWMA se kitna stretched. Recent bars zyada weight "
        "mein hain, reactive momentum reading."
    ),
    tags=["momentum", "lwma"],
    calculation_function="price_momentum_index",
)


_TREND_MOMENTUM_COMBO = IndicatorMetadata(
    id="trend_momentum_combo",
    name="Trend-Momentum Combo",
    category="Momentum",
    description=(
        "trend_dir * momentum_in_atr_units. Positive = momentum "
        "aligned with trend (continuation); negative = momentum "
        "against trend (counter-trend setup)."
    ),
    inputs=[
        InputSpec(name="trend_period", type=InputType.NUMBER, default=50, min=2, max=400),
        InputSpec(name="momentum_period", type=InputType.NUMBER, default=14, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Trend-Momentum Combo = trend direction * momentum. "
        "Positive = aligned (continuation), negative = against "
        "(reversal candidate)."
    ),
    tags=["momentum", "trend", "combo"],
    calculation_function="trend_momentum_combo",
)


# --- Volume Completers (3) -----------------------------------------


_VOLUME_ZONE_OSCILLATOR = IndicatorMetadata(
    id="volume_zone_oscillator",
    name="Volume Zone Oscillator (VZO)",
    category="Volume",
    description=(
        "Walid Khalil's VZO. EMA(signed-volume) / EMA(volume) * "
        "100. Range typically [-60, +60]. >40 bullish zone, "
        "<-40 bearish zone."
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
        "VZO = volume ka direction-weighted ratio. >40 bullish "
        "zone, <-40 bearish, beech mein neutral."
    ),
    tags=["volume", "vzo", "khalil"],
    calculation_function="volume_zone_oscillator",
)


_PVI_SIGNAL = IndicatorMetadata(
    id="positive_volume_index_signal",
    name="PVI Signal Line",
    category="Volume",
    description=(
        "EMA of Pack 10's positive_volume_index. Default 255-bar "
        "(Fosback's 1-year window). PVI > signal = bullish retail "
        "flow (Fosback's framework)."
    ),
    inputs=[
        InputSpec(name="signal_period", type=InputType.NUMBER, default=255, min=2, max=2000),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "PVI Signal Line = EMA of PVI. PVI signal ke upar = "
        "retail flow bullish (Fosback Smart-Dumb framework)."
    ),
    tags=["volume", "pvi", "fosback"],
    calculation_function="positive_volume_index_signal",
)


_NVI_SIGNAL = IndicatorMetadata(
    id="negative_volume_index_signal",
    name="NVI Signal Line",
    category="Volume",
    description=(
        "EMA of Pack 10's negative_volume_index. Default 255-bar "
        "(Fosback's 1-year window). NVI > signal = bullish "
        "institutional flow ('Smart Money')."
    ),
    inputs=[
        InputSpec(name="signal_period", type=InputType.NUMBER, default=255, min=2, max=2000),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "NVI Signal Line = EMA of NVI. NVI signal ke upar = "
        "smart-money flow bullish."
    ),
    tags=["volume", "nvi", "fosback"],
    calculation_function="negative_volume_index_signal",
)


# --- India-Specific (3, 2 stubs) ----------------------------------


_FNO_LOT_SIZE_ATR = IndicatorMetadata(
    id="fno_lot_size_atr",
    name="F&O Lot-Size ATR",
    category="Risk",
    description=(
        "ATR * assumed F&O lot size = per-contract rupee risk. "
        "Default lot=50 (legacy NIFTY); operators should override "
        "per latest exchange circular."
    ),
    inputs=[
        InputSpec(name="atr_period", type=InputType.NUMBER, default=14, min=2, max=200),
        InputSpec(
            name="assumed_lot_size", type=InputType.NUMBER,
            default=50, min=1, max=100000,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "F&O Lot-Size ATR = ATR * lot size. Per-contract rupee "
        "risk. Position sizing ke liye natural unit."
    ),
    tags=["risk", "fno", "india"],
    calculation_function="fno_lot_size_atr",
)


_NSE_BSE_ARBITRAGE_PROXY = IndicatorMetadata(
    id="nse_bse_arbitrage_proxy",
    name="NSE/BSE Arbitrage Proxy (stub)",
    category="Arbitrage",
    description=(
        "Spread between NSE and BSE for the same symbol. "
        "**Phase 1 STUB** - returns all-None until the data-"
        "provider exposes a parallel-exchange feed (Phase 2)."
    ),
    inputs=[
        InputSpec(
            name="spread_threshold_pct", type=InputType.NUMBER,
            default=0.1, min=0.001, max=10.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "NSE/BSE Arbitrage Proxy = dono exchanges ka spread. "
        "Phase 1 mein stub - parallel feed Phase 2 mein."
    ),
    tags=["arbitrage", "india", "stub"],
    calculation_function="nse_bse_arbitrage_proxy",
)


_NIFTY_50_RELATIVE_POSITION = IndicatorMetadata(
    id="nifty_50_relative_position",
    name="NIFTY 50 Relative Position (stub)",
    category="Relative Strength",
    description=(
        "Symbol % return - NIFTY 50 % return over `lookback` bars. "
        "**Phase 1 STUB** - needs symbol-to-NIFTY-component "
        "mapping + NIFTY candles (Phase 2)."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=30, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "NIFTY 50 Relative Position = symbol vs NIFTY return "
        "spread. Phase 1 mein stub - symbol mapping Phase 2 mein."
    ),
    tags=["relative-strength", "india", "stub"],
    calculation_function="nifty_50_relative_position",
)


# --- Aggregate -----------------------------------------------------


PACK18_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _TTM_SQUEEZE,
    _TTM_SQUEEZE_PRO,
    _WEEKLY_TREND_STRENGTH,
    _TREND_AGE_BARS,
    _CONSECUTIVE_HIGHER_LOWS,
    _ROC_SMOOTHED,
    _MOMENTUM_OSCILLATOR,
    _PRICE_MOMENTUM_INDEX,
    _TREND_MOMENTUM_COMBO,
    _VOLUME_ZONE_OSCILLATOR,
    _PVI_SIGNAL,
    _NVI_SIGNAL,
    _FNO_LOT_SIZE_ATR,
    _NSE_BSE_ARBITRAGE_PROXY,
    _NIFTY_50_RELATIVE_POSITION,
)


__all__ = ["PACK18_ACTIVE_INDICATORS"]
