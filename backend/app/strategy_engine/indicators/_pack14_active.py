"""Pack 14 - 12 statistical + regression + advanced math indicators.

No discovery-time collisions on indicator ids. Several
conceptual relatives that ship as distinct + complementary:

    * ``linear_regression_slope`` projects the existing
      ``linear_regression`` calc into the slope output (same
      pattern as Pack 7's aroon_up/down/oscillator on the
      existing ``aroon`` calc).
    * ``spectral_dominant_period`` shares the "what's the
      dominant cycle" question with Pack 11's
      ``dominant_cycle_period`` (Hilbert) but uses a different
      mechanism (FFT). Cross-check + complementary signal.
    * ``half_life_mean_reversion`` and Pack 5's
      ``hurst_exponent`` both characterise mean-reversion
      tendency but in different units (bars-to-revert vs
      dimensionless 0..1 persistence index).
    * ``correlation_with_volume`` (Pack 13) and
      ``autocorrelation`` are different tools — one is
      cross-series, the other within-series at a lag.

NO new Pine importer wiring - none of Pack 14's indicators have
a standard Pine v5 ``ta.*`` equivalent (Pine ``ta.linreg``
emits the line value, not the slope; FFT and OU half-life have
no Pine builtin). Lock test ``test_pack14_has_no_pine_aliases``
pins the contract.

Honest scope notes:

* ``spectral_dominant_period`` uses a pure-Python DFT (no numpy
  dependency). O(N^2) per bar; fine at the default 64-bar
  window. For windows > 256 a Phase-2 numpy migration would
  pay off.
* ``polynomial_regression_2`` and ``polynomial_regression_3``
  use direct normal-equation solve (Gaussian elimination on
  3x3 / 4x4 matrices) - no numpy dependency, deterministic.
* ``variance_ratio`` follows Lo-MacKinlay (1988); the period
  is automatically scaled to ``long * 10`` so the variance
  estimates have a meaningful sample size.
* ``half_life_mean_reversion`` returns ``None`` when the OU
  slope is non-negative (series is trending or random-walk-
  like - no mean reversion to estimate). Caller branches.

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT):

    INTERMEDIATE (2) - linear_regression_slope, r_squared
    EXPERT (10)      - skewness, kurtosis,
                       polynomial_regression_2/3,
                       exponential_regression,
                       logarithmic_regression,
                       variance_ratio, autocorrelation,
                       spectral_dominant_period,
                       half_life_mean_reversion
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

# --- Statistical (4) ------------------------------------------------


_LINEAR_REGRESSION_SLOPE = IndicatorMetadata(
    id="linear_regression_slope",
    name="Linear Regression Slope",
    category="Statistical",
    description=(
        "OLS slope of the trailing-window linear-regression fit. "
        "Per-bar drift; positive = uptrending best-fit, negative "
        "= downtrending. Companion to the existing "
        "``linear_regression`` (which emits the line value)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Linear Regression Slope = trend speed (per bar). Positive "
        "+ rising = momentum building; flipping sign = trend "
        "change candidate."
    ),
    tags=["statistical", "regression"],
    calculation_function="linear_regression_slope",
)


_R_SQUARED = IndicatorMetadata(
    id="r_squared",
    name="R-squared",
    category="Statistical",
    description=(
        "Coefficient of determination of the trailing-window "
        "linear-regression fit. Range [0, 1]; 1 = perfect linear "
        "fit, 0 = no linear relationship. Trend-purity filter."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=14, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "R-squared = trend kitna 'clean' hai. 0.7+ = strong "
        "trending regime (use trend-following strategies); "
        "<0.3 = chop / non-linear (mean-reversion territory)."
    ),
    tags=["statistical", "regression"],
    calculation_function="r_squared",
)


_SKEWNESS = IndicatorMetadata(
    id="skewness",
    name="Return Skewness",
    category="Statistical",
    description=(
        "Third standardised moment of trailing-window returns. "
        "< 0 = left-tail risk (negative skew); > 0 = right-tail "
        "lottery-like upside; ~ 0 = symmetric."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=3, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Skewness return distribution ka 'lopsidedness'. Negative "
        "= big down-moves zyada (left-tail risk warning); "
        "positive = big up-moves zyada (lottery profile)."
    ),
    tags=["statistical", "moments"],
    calculation_function="skewness",
)


_KURTOSIS = IndicatorMetadata(
    id="kurtosis",
    name="Return Kurtosis (excess)",
    category="Statistical",
    description=(
        "Excess kurtosis (fourth moment - 3) of trailing-window "
        "returns. > 0 = fat-tailed (more extreme moves than "
        "Gaussian); < 0 = thin-tailed."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=4, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Excess Kurtosis = fat-tail risk. Positive = extreme "
        "moves common (fat tails); near zero = Gaussian-like; "
        "negative = predictable + bounded."
    ),
    tags=["statistical", "moments"],
    calculation_function="kurtosis",
)


# --- Regression Variants (4) ----------------------------------------


_POLYNOMIAL_REGRESSION_2 = IndicatorMetadata(
    id="polynomial_regression_2",
    name="Polynomial Regression (degree 2)",
    category="Regression",
    description=(
        "Quadratic polynomial fit value at the trailing-window "
        "end. Curvilinear smoother that captures concave / "
        "convex trends the linear regression can't."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=3, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Polynomial Regression (2) = quadratic trend fit. Linear "
        "regression se zyada flexible — accelerating / "
        "decelerating trends capture karta hai."
    ),
    tags=["regression", "polynomial"],
    calculation_function="polynomial_regression_2",
)


_POLYNOMIAL_REGRESSION_3 = IndicatorMetadata(
    id="polynomial_regression_3",
    name="Polynomial Regression (degree 3)",
    category="Regression",
    description=(
        "Cubic polynomial fit value at the trailing-window end. "
        "Captures S-shaped trends with inflection points."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=4, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.OVERLAY,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Polynomial Regression (3) = cubic fit. Inflection points "
        "capture karta hai — double tops / bottoms ke fit ke liye "
        "useful."
    ),
    tags=["regression", "polynomial"],
    calculation_function="polynomial_regression_3",
)


_EXPONENTIAL_REGRESSION = IndicatorMetadata(
    id="exponential_regression",
    name="Exponential Regression Slope",
    category="Regression",
    description=(
        "Slope coefficient ``b`` from fitting ``y = a * exp(b*x)`` "
        "to the trailing window. Per-bar exponential growth rate; "
        "> 0 = compounding growth, < 0 = exponential decay."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Exponential Regression slope = compounding growth rate. "
        "Useful for high-growth stocks ya commodities (linear "
        "regression understates such trends)."
    ),
    tags=["regression", "exponential"],
    calculation_function="exponential_regression",
)


_LOGARITHMIC_REGRESSION = IndicatorMetadata(
    id="logarithmic_regression",
    name="Logarithmic Regression Slope",
    category="Regression",
    description=(
        "Slope coefficient ``b`` from fitting ``y = a + b*log(x+1)`` "
        "to the trailing window. Captures decelerating "
        "(square-root-ish) growth."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=2, max=500),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Logarithmic Regression slope = decelerating growth rate. "
        "Long-term saturation phases ke liye fit (e.g. mature "
        "blue-chips)."
    ),
    tags=["regression", "logarithmic"],
    calculation_function="logarithmic_regression",
)


# --- Advanced Math (4) ----------------------------------------------


_VARIANCE_RATIO = IndicatorMetadata(
    id="variance_ratio",
    name="Variance Ratio (Lo-MacKinlay)",
    category="Statistical",
    description=(
        "Var(long-horizon returns) / (long/short * Var(short-"
        "horizon returns)). ~ 1.0 = random walk; > 1.0 = "
        "trending (positive autocorrelation); < 1.0 = mean-"
        "reverting (negative autocorrelation)."
    ),
    inputs=[
        InputSpec(name="short", type=InputType.NUMBER, default=2, min=1, max=200),
        InputSpec(name="long", type=InputType.NUMBER, default=10, min=2, max=500),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Variance Ratio (Lo-MacKinlay 1988) = random-walk test. "
        "1.0 = pure random walk, > 1 = trending, < 1 = mean-"
        "reverting. Strategy regime selector."
    ),
    tags=["statistical", "regime"],
    calculation_function="variance_ratio",
)


_AUTOCORRELATION = IndicatorMetadata(
    id="autocorrelation",
    name="Return Autocorrelation",
    category="Statistical",
    description=(
        "Autocorrelation of returns at lag N over a trailing "
        "window. Range [-1, +1]; positive at lag 1 = momentum, "
        "negative = mean-reversion."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=30, min=3, max=500),
        InputSpec(name="lag", type=InputType.NUMBER, default=1, min=1, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Autocorrelation = returns ka self-similarity lag-N pe. "
        "+0.3+ at lag=1 = momentum strategies favor; -0.3- = "
        "mean-reversion strategies."
    ),
    tags=["statistical", "autocorrelation"],
    calculation_function="autocorrelation",
)


_SPECTRAL_DOMINANT_PERIOD = IndicatorMetadata(
    id="spectral_dominant_period",
    name="Spectral Dominant Period (FFT)",
    category="Cycle",
    description=(
        "FFT-based estimate of the dominant cycle period. "
        "Distinct mechanism from Pack 11's "
        "``dominant_cycle_period`` (Hilbert Transform); useful "
        "as a cross-check."
    ),
    inputs=[
        InputSpec(name="window", type=InputType.NUMBER, default=64, min=8, max=1024),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Spectral Dominant Period = FFT se dominant cycle "
        "period. Hilbert-based estimate ke saath cross-check, "
        "transition zones mein different signal de sakta hai."
    ),
    tags=["cycle", "fft"],
    calculation_function="spectral_dominant_period",
)


_HALF_LIFE_MEAN_REVERSION = IndicatorMetadata(
    id="half_life_mean_reversion",
    name="Mean-Reversion Half-Life (OU)",
    category="Statistical",
    description=(
        "Bars-to-revert-half-way estimate from the Ornstein-"
        "Uhlenbeck regression. ``None`` when the series isn't "
        "mean-reverting (OU slope >= 0)."
    ),
    inputs=[
        InputSpec(name="period", type=InputType.NUMBER, default=60, min=10, max=1000),
        InputSpec(name="source", type=InputType.SOURCE, default="close"),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Half-Life mean-reversion ke liye = kitne bars mein "
        "price half distance se mean tak revert karega. Smaller "
        "= faster reversion. None = trending (no reversion)."
    ),
    tags=["statistical", "mean-reversion"],
    calculation_function="half_life_mean_reversion",
)


# --- Aggregate -------------------------------------------------------


PACK14_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _LINEAR_REGRESSION_SLOPE,
    _R_SQUARED,
    _SKEWNESS,
    _KURTOSIS,
    _POLYNOMIAL_REGRESSION_2,
    _POLYNOMIAL_REGRESSION_3,
    _EXPONENTIAL_REGRESSION,
    _LOGARITHMIC_REGRESSION,
    _VARIANCE_RATIO,
    _AUTOCORRELATION,
    _SPECTRAL_DOMINANT_PERIOD,
    _HALF_LIFE_MEAN_REVERSION,
)


__all__ = ["PACK14_ACTIVE_INDICATORS"]
