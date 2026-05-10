"""Pack 16 - 12 options-aware + Greeks-proxy indicators.

⚠️  CRITICAL: All Pack 16 "Greeks" are PRICE-DERIVED PROXIES,
NOT actual Black-Scholes Greeks. Real Greeks need: options
chain, strike, expiry, IV (per option), risk-free rate. None
of those are at the calc-layer abstraction. Phase 2 wiring
with a real options-feed will add actual Greeks; Pack 16
proxies stay useful as the price-only fallback.

Discovery-time near-collision (handled honestly):

    * The spec's ``weekly_pivot_distance`` would have computed
      the same numbers as Pack 8's already-active
      ``weekly_pivot_close``. Same Pack 10 lesson - duplicate
      calc under a different name is LOC without signal.
      -> substituted with ``monthly_pivot_distance`` (same
        shape but on calendar month - useful for swing
        strategies, complementary to weekly).

Honest Phase-1 stub (Pack 8 / 10 / 13 lesson):

    * ``vix_correlation`` requires a parallel VIX (or India VIX)
      candle series at the calc-layer abstraction. The data-
      provider doesn't expose that yet. Ships as no-op
      returning all-None, with HAS_VIX_CONTEXT = False flag.
      Test asserts the contract.

Honest scope notes (per indicator + here):

* ``iv_proxy_atr`` is annualised ATR-percent volatility. NOT
  real IV. The third member of the family alongside
  historical_volatility (close-to-close stddev) and
  parkinson_volatility (high-low range) - same units (%
  annualised), different mechanism.
* ``iv_rank`` and ``iv_percentile`` use ``iv_proxy_atr`` as
  their underlying. Both are popular options-trading concepts
  with slightly different formulas (range vs distribution
  ranking) - ship both per Tastyworks convention.
* ``atm_strike_distance``, ``round_number_attraction`` use a
  configurable ``strike_step`` (default 100 = NIFTY-style).
  Operator picks the right grid for their symbol.
* ``expiry_day_volatility`` is a single-symbol proxy. Real
  expiry-day vol surge involves options-OI dynamics not
  visible at the price-data layer.
* ``delta/theta/vega/gamma_proxy_*`` are price-derived
  approximations of the *concepts* the Greeks measure. Real
  Greeks come from Black-Scholes inversion on actual option
  prices. Documented loudly in each calc module.

NO new Pine importer wiring - none of Pack 16's indicators have
a standard Pine v5 ``ta.*`` equivalent (custom proxies all the
way down). Lock test ``test_pack16_has_no_pine_aliases`` pins
the contract.

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT):

    INTERMEDIATE (5) - iv_rank, iv_percentile,
                       atm_strike_distance,
                       round_number_attraction,
                       monthly_pivot_distance
    EXPERT (7)       - iv_proxy_atr, vix_correlation (stub),
                       expiry_day_volatility,
                       delta_proxy_directional,
                       theta_proxy_decay,
                       vega_proxy_iv_sensitivity,
                       gamma_proxy_acceleration
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

# --- IV Proxies (4) -------------------------------------------------


_IV_PROXY_ATR = IndicatorMetadata(
    id="iv_proxy_atr",
    name="IV Proxy (ATR-based)",
    category="Volatility",
    description=(
        "Annualised ATR-percent volatility. PROXY, not real IV "
        "(which needs an options chain). Third estimator in the "
        "family alongside historical_volatility (stddev) and "
        "parkinson_volatility (range)."
    ),
    inputs=[
        InputSpec(name="atr_period", type=InputType.NUMBER, default=20, min=2, max=200),
        InputSpec(
            name="bars_per_year", type=InputType.NUMBER,
            default=252, min=1, max=525600,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "IV Proxy ATR-based = ATR% ko annualise karke real IV "
        "ke units mein lana. NOT real IV - actual IV options "
        "chain se Black-Scholes inversion karke milta hai."
    ),
    tags=["volatility", "iv", "proxy"],
    calculation_function="iv_proxy_atr",
)


_IV_RANK = IndicatorMetadata(
    id="iv_rank",
    name="IV Rank",
    category="Volatility",
    description=(
        "(current - min) / (max - min) * 100 of iv_proxy_atr "
        "over trailing window. 0-100 range. Tastyworks-style "
        "rank vs trailing high/low."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=252, min=2, max=2000),
        InputSpec(name="atr_period", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "IV Rank = current vol-proxy trailing range mein kahan "
        "baith raha hai. >70 = high IV (sell-vol setups), <30 "
        "= low IV (buy-vol setups)."
    ),
    tags=["volatility", "iv", "rank"],
    calculation_function="iv_rank",
)


_IV_PERCENTILE = IndicatorMetadata(
    id="iv_percentile",
    name="IV Percentile",
    category="Volatility",
    description=(
        "% of trailing iv_proxy_atr readings <= current. 0-100 "
        "range. Distribution-based ranking (more outlier-robust "
        "than IV Rank's range method)."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=252, min=2, max=2000),
        InputSpec(name="atr_period", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "IV Percentile = ratio of historic readings <= current. "
        "Outliers se kam affected hota hai. >80 = vol elevated "
        "vs history."
    ),
    tags=["volatility", "iv", "percentile"],
    calculation_function="iv_percentile",
)


_VIX_CORRELATION = IndicatorMetadata(
    id="vix_correlation",
    name="VIX Correlation (stub)",
    category="Volatility",
    description=(
        "Rolling Pearson correlation of close vs VIX. "
        "**Phase 1 STUB** - returns all-None until the data-"
        "provider exposes a VIX-series fetch (Phase 2)."
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
        "VIX Correlation = stock close vs INDIA VIX correlation. "
        "Phase 1 mein abhi stub - data-provider wiring Phase 2 "
        "mein. None series milega tab tak."
    ),
    tags=["volatility", "vix", "stub"],
    calculation_function="vix_correlation",
)


# --- Options Activity Proxies (4) -----------------------------------


_ATM_STRIKE_DISTANCE = IndicatorMetadata(
    id="atm_strike_distance",
    name="ATM Strike Distance",
    category="Options",
    description=(
        "% distance from the nearest options-strike grid level "
        "(integer multiple of strike_step). Default 100 = "
        "NIFTY-style strikes; use 50 for BANKNIFTY index."
    ),
    inputs=[
        InputSpec(
            name="strike_step", type=InputType.NUMBER,
            default=100.0, min=0.01, max=10000.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "ATM Strike Distance = nearest strike se kitne %. Options "
        "strategies ko ATM ke aas-paas position lene ke liye "
        "useful."
    ),
    tags=["options", "strike"],
    calculation_function="atm_strike_distance",
)


_ROUND_NUMBER_ATTRACTION = IndicatorMetadata(
    id="round_number_attraction",
    name="Round Number Attraction",
    category="Options",
    description=(
        "1.0 when close is within threshold_pct of nearest round-"
        "number strike (default 0.5%). Flags psychological-level + "
        "options-OI clusters."
    ),
    inputs=[
        InputSpec(
            name="strike_step", type=InputType.NUMBER,
            default=100.0, min=0.01, max=10000.0,
        ),
        InputSpec(
            name="threshold_pct", type=InputType.NUMBER,
            default=0.5, min=0.01, max=10.0,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Round Number Attraction = price round-number strike ke "
        "0.5% andar hai? Yeh psychological + options-OI levels - "
        "consolidation / reversal probable hota hai."
    ),
    tags=["options", "psychology"],
    calculation_function="round_number_attraction",
)


_EXPIRY_DAY_VOLATILITY = IndicatorMetadata(
    id="expiry_day_volatility",
    name="Expiry Day Volatility Proxy",
    category="Options",
    description=(
        "Today's session range vs typical session range on the "
        "configured expiry weekday (default Thursday). >1 = "
        "elevated vs history; <1 = subdued. Single-symbol proxy."
    ),
    inputs=[
        InputSpec(
            name="weekday_target", type=InputType.NUMBER,
            default=3, min=0, max=6,
        ),
        InputSpec(
            name="history_sessions", type=InputType.NUMBER,
            default=4, min=2, max=52,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Expiry Day Vol Proxy = aaj ka range vs typical Thursday "
        "range. >1.5 = expiry day vol surge, options sellers ke "
        "liye risk."
    ),
    tags=["options", "expiry", "proxy"],
    calculation_function="expiry_day_volatility",
)


_MONTHLY_PIVOT_DISTANCE = IndicatorMetadata(
    id="monthly_pivot_distance",
    name="Monthly Pivot Distance",
    category="Pivot",
    description=(
        "% distance from prior month's classic pivot "
        "(H+L+C)/3. Sibling of Pack 8's weekly_pivot_close at a "
        "longer timeframe - useful for swing strategies."
    ),
    inputs=[
        InputSpec(
            name="months_back", type=InputType.NUMBER,
            default=1, min=1, max=12,
        ),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Monthly Pivot Distance = pichle mahine ke pivot se "
        "kitne %. Swing strategies ke liye macro-level filter "
        "(weekly version Pack 8 mein hai)."
    ),
    tags=["pivot", "monthly"],
    calculation_function="monthly_pivot_distance",
)


# --- Greeks-Style Proxies (4) ---------------------------------------


_DELTA_PROXY_DIRECTIONAL = IndicatorMetadata(
    id="delta_proxy_directional",
    name="Delta Proxy (Directional Bias)",
    category="Options",
    description=(
        "PROXY (not Black-Scholes delta). -1..+1 directional "
        "bias from (close - SMA) / (2 * ATR), clamped. "
        "Approximates the *concept* of delta using price action."
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
        "Delta Proxy = price ka SMA se distance ATR-units mein, "
        "clamped -1..+1. NOT Black-Scholes delta - real delta "
        "options chain ke bina nahi nikal sakta."
    ),
    tags=["options", "greeks", "proxy"],
    calculation_function="delta_proxy_directional",
)


_THETA_PROXY_DECAY = IndicatorMetadata(
    id="theta_proxy_decay",
    name="Theta Proxy (Range Decay)",
    category="Options",
    description=(
        "PROXY (not Black-Scholes theta). Avg range first half "
        "vs second half of trailing window. Positive = ranges "
        "shrinking (decay regime)."
    ),
    inputs=[
        InputSpec(name="lookback", type=InputType.NUMBER, default=20, min=4, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Theta Proxy = ranges shrink ho rahe hain ya expand. "
        "Positive = decay regime (sellers favored), negative = "
        "vol-of-vol rising (buyers favored)."
    ),
    tags=["options", "greeks", "proxy"],
    calculation_function="theta_proxy_decay",
)


_VEGA_PROXY_IV_SENSITIVITY = IndicatorMetadata(
    id="vega_proxy_iv_sensitivity",
    name="Vega Proxy (Vol-Regime Sensitivity)",
    category="Options",
    description=(
        "PROXY (not Black-Scholes vega). Price change % per "
        "unit change in short/long ATR ratio. Approximates "
        "sensitivity to volatility-regime shifts."
    ),
    inputs=[
        InputSpec(name="short", type=InputType.NUMBER, default=5, min=2, max=200),
        InputSpec(name="long", type=InputType.NUMBER, default=20, min=3, max=400),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Vega Proxy = vol regime shift ke saath price kitna move "
        "karta hai. High |value| = vol-sensitive symbol."
    ),
    tags=["options", "greeks", "proxy"],
    calculation_function="vega_proxy_iv_sensitivity",
)


_GAMMA_PROXY_ACCELERATION = IndicatorMetadata(
    id="gamma_proxy_acceleration",
    name="Gamma Proxy (Price Acceleration)",
    category="Options",
    description=(
        "PROXY (not Black-Scholes gamma). Smoothed second-"
        "difference of close = price acceleration. Positive = "
        "accelerating up; negative = accelerating down / "
        "decelerating up."
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
        "Gamma Proxy = price acceleration (second derivative). "
        "Strong moves accelerate; reversals decelerate first "
        "before flipping."
    ),
    tags=["options", "greeks", "proxy"],
    calculation_function="gamma_proxy_acceleration",
)


# --- Aggregate -------------------------------------------------------


PACK16_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _IV_PROXY_ATR,
    _IV_RANK,
    _IV_PERCENTILE,
    _VIX_CORRELATION,
    _ATM_STRIKE_DISTANCE,
    _ROUND_NUMBER_ATTRACTION,
    _EXPIRY_DAY_VOLATILITY,
    _MONTHLY_PIVOT_DISTANCE,
    _DELTA_PROXY_DIRECTIONAL,
    _THETA_PROXY_DECAY,
    _VEGA_PROXY_IV_SENSITIVITY,
    _GAMMA_PROXY_ACCELERATION,
)


__all__ = ["PACK16_ACTIVE_INDICATORS"]
