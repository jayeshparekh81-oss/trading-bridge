"""Pack 14 - statistical + regression + advanced math tests.

Same shape as Pack 2-13. Active count assertion ``>= 179``.

Several tests assert *qualitative* properties (positive slope on
uptrend, R^2 ~ 1 on a clean line, finite half-life on mean-
reverting series). The cycle / FFT indicators get a "produces
defined output in band" check rather than byte-matching - the
spectral period from a synthetic sine wave should be close to
the input wave length.

No new Pine wiring; pinned by the Pack 14 lock test.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack14_active import (
    PACK14_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.autocorrelation import (
    autocorrelation,
)
from app.strategy_engine.indicators.calculations.exponential_regression import (
    exponential_regression,
)
from app.strategy_engine.indicators.calculations.half_life_mean_reversion import (
    half_life_mean_reversion,
)
from app.strategy_engine.indicators.calculations.kurtosis import kurtosis
from app.strategy_engine.indicators.calculations.linear_regression_slope import (
    linear_regression_slope,
)
from app.strategy_engine.indicators.calculations.logarithmic_regression import (
    logarithmic_regression,
)
from app.strategy_engine.indicators.calculations.polynomial_regression_2 import (
    polynomial_regression_2,
)
from app.strategy_engine.indicators.calculations.polynomial_regression_3 import (
    polynomial_regression_3,
)
from app.strategy_engine.indicators.calculations.r_squared import r_squared
from app.strategy_engine.indicators.calculations.skewness import skewness
from app.strategy_engine.indicators.calculations.spectral_dominant_period import (
    spectral_dominant_period,
)
from app.strategy_engine.indicators.calculations.variance_ratio import (
    variance_ratio,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# --- Statistical (4) ------------------------------------------------


def test_linear_regression_slope_constant_yields_zero() -> None:
    out = linear_regression_slope(values=[100.0] * 30, period=14)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


def test_linear_regression_slope_positive_on_uptrend() -> None:
    out = linear_regression_slope(
        values=[100.0 + i for i in range(30)], period=14,
    )
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(1.0, abs=1e-6)


def test_r_squared_perfect_line_yields_one() -> None:
    out = r_squared(values=[100.0 + i for i in range(30)], period=14)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(1.0, abs=1e-6) for v in defined)


def test_r_squared_constant_yields_zero() -> None:
    """Constant input -> Syy = 0 -> R^2 = 0 by our convention."""
    out = r_squared(values=[100.0] * 30, period=14)
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_skewness_constant_input_returns_none() -> None:
    """Constant closes -> zero variance -> skew undefined."""
    out = skewness(closes=[100.0] * 50, period=30)
    assert all(v is None for v in out)


def test_skewness_returns_finite_on_synthetic_data() -> None:
    """Returns produced by a wavy series should yield a finite skew."""
    n = 100
    closes = [100.0 + math.sin(i * 0.3) * 5.0 for i in range(n)]
    out = skewness(closes=closes, period=30)
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(math.isfinite(v) for v in defined)


def test_kurtosis_constant_input_returns_none() -> None:
    out = kurtosis(closes=[100.0] * 50, period=30)
    assert all(v is None for v in out)


def test_kurtosis_returns_finite_on_synthetic_data() -> None:
    n = 100
    closes = [100.0 + math.sin(i * 0.3) * 5.0 for i in range(n)]
    out = kurtosis(closes=closes, period=30)
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(math.isfinite(v) for v in defined)


# --- Regression Variants (4) ----------------------------------------


def test_polynomial_regression_2_returns_close_to_linear_on_line() -> None:
    """For a perfect line, the quadratic fit's c coefficient is
    ~0 and the value at the end matches the line."""
    n = 30
    out = polynomial_regression_2(
        values=[100.0 + i for i in range(n)], period=20,
    )
    last = out[-1]
    assert last is not None
    # End of window (k = period - 1, so x = 19 in window-local
    # coords; corresponds to closes[n-1] = 129).
    assert last == pytest.approx(129.0, abs=1e-6)


def test_polynomial_regression_2_rejects_short_period() -> None:
    with pytest.raises(ValueError, match=">= 3"):
        polynomial_regression_2(values=[1.0] * 30, period=2)


def test_polynomial_regression_3_rejects_short_period() -> None:
    with pytest.raises(ValueError, match=">= 4"):
        polynomial_regression_3(values=[1.0] * 30, period=3)


def test_polynomial_regression_3_returns_finite_on_synthetic() -> None:
    n = 60
    out = polynomial_regression_3(
        values=[100.0 + math.sin(i * 0.3) * 5.0 for i in range(n)],
        period=30,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(math.isfinite(v) for v in defined)


def test_exponential_regression_positive_on_growth() -> None:
    """y = exp(0.05 * x) -> slope b = 0.05."""
    n = 50
    out = exponential_regression(
        values=[math.exp(0.05 * i) for i in range(n)], period=30,
    )
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(0.05, abs=1e-6)


def test_exponential_regression_skips_nonpositive_window() -> None:
    """A window with any value <= 0 returns None (log undefined)."""
    out = exponential_regression(values=[100.0] * 29 + [0.0], period=30)
    last = out[-1]
    assert last is None


def test_logarithmic_regression_recovers_slope_on_first_window() -> None:
    """The fit is local: ``y = a + b * log(k+1)`` with ``k = 0..period-1``
    (window-local index, NOT global series index). So to recover
    ``b = 2`` we feed the FIRST window with values ``2*log(k+1)``;
    the result lands at ``out[period - 1]`` (the first defined
    index). Subsequent bars fit a different window and won't
    necessarily recover 2."""
    period = 30
    values = [2.0 * math.log(k + 1) for k in range(period)] + [0.0] * 20
    out = logarithmic_regression(values=values, period=period)
    first_defined = out[period - 1]
    assert first_defined is not None
    assert first_defined == pytest.approx(2.0, abs=1e-6)


# --- Advanced Math (4) ----------------------------------------------


def test_variance_ratio_rejects_short_geq_long() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        variance_ratio(closes=[1.0] * 200, short=10, long=10)


def test_variance_ratio_returns_finite_on_synthetic() -> None:
    """For the default short=2, long=10, we need long*10 + long
    bars minimum (= 110)."""
    n = 200
    out = variance_ratio(
        closes=[100.0 + math.sin(i * 0.2) for i in range(n)],
        short=2, long=10,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(math.isfinite(v) and v > 0 for v in defined)


def test_autocorrelation_rejects_lag_geq_period() -> None:
    with pytest.raises(ValueError, match="period must be > lag"):
        autocorrelation(closes=[1.0] * 100, period=5, lag=5)


def test_autocorrelation_returns_in_range() -> None:
    n = 100
    out = autocorrelation(
        closes=[100.0 + (i % 7) for i in range(n)], period=30, lag=1,
    )
    defined = [v for v in out if v is not None]
    assert all(-1.0 - 1e-9 <= v <= 1.0 + 1e-9 for v in defined)


def test_spectral_dominant_period_recovers_known_cycle() -> None:
    """Pure 16-bar sine wave should yield a dominant period near 16."""
    n = 200
    closes = [100.0 + 5.0 * math.sin(2.0 * math.pi * i / 16.0) for i in range(n)]
    out = spectral_dominant_period(closes=closes, window=64)
    last = out[-1]
    assert last is not None
    # FFT bin resolution at window=64 is N/k for integer k, so the
    # 16-bar cycle should recover to exactly 16 (k=4).
    assert last == pytest.approx(16.0, abs=1.0)


def test_spectral_dominant_period_rejects_small_window() -> None:
    with pytest.raises(ValueError, match=">= 8"):
        spectral_dominant_period(closes=[1.0] * 100, window=4)


def test_half_life_finite_on_mean_reverting_series() -> None:
    """OU process generated via known half-life ~ 10 bars should
    estimate a finite, positive half-life."""
    n = 200
    # delta_y = -0.1 * y + small noise (using deterministic
    # alternating "noise" to keep the test reproducible).
    y = 0.0
    closes = []
    for i in range(n):
        noise = 0.5 if i % 2 == 0 else -0.5
        y = y + (-0.1 * y) + noise
        closes.append(100.0 + y)
    out = half_life_mean_reversion(closes=closes, period=60)
    last = out[-1]
    assert last is not None
    assert math.isfinite(last) and last > 0


def test_half_life_returns_none_on_monotone_uptrend() -> None:
    """Pure trend has positive OU slope -> no mean reversion -> None."""
    out = half_life_mean_reversion(
        closes=[100.0 + i for i in range(200)], period=60,
    )
    # Late bars should all be None (no mean reversion in this series).
    assert out[-1] is None


# --- Registry promotion ---------------------------------------------


_PACK14_IDS = {
    "linear_regression_slope",
    "r_squared",
    "skewness",
    "kurtosis",
    "polynomial_regression_2",
    "polynomial_regression_3",
    "exponential_regression",
    "logarithmic_regression",
    "variance_ratio",
    "autocorrelation",
    "spectral_dominant_period",
    "half_life_mean_reversion",
}


def test_pack14_module_exposes_twelve_indicators() -> None:
    assert len(PACK14_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK14_ACTIVE_INDICATORS} == _PACK14_IDS


def test_pack14_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK14_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack14_is_one_hundred_seventy_nine() -> None:
    """Pack-13 baseline 167 + 12 Pack 14 = 179."""
    assert len(get_active_indicators()) >= 179


def test_pack14_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK14_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack14_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK14_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


def test_pack14_has_no_pine_aliases() -> None:
    """Pack 14 ships no Pine wiring - none of the indicators have
    a standard Pine v5 ta.* equivalent."""
    for meta in PACK14_ACTIVE_INDICATORS:
        assert meta.pine_aliases == [], (
            f"{meta.id} unexpectedly has Pine aliases: {meta.pine_aliases}"
        )


# --- Backtest dispatch ----------------------------------------------


def _wavy_candles(n: int = 200) -> list:
    """Synthetic OHLC large enough for the variance_ratio
    indicator (needs long*10 + long = 110 bars min) + the
    spectral_dominant_period default 64-bar window."""
    out = []
    for i in range(n):
        base = 100.0 + math.sin(i * 0.2) * 3.0 + (i % 5) * 0.2
        out.append(
            make_candle(
                minutes=i,
                open_=base,
                high=base + 1.5,
                low=base - 1.5,
                close=base + 0.5,
                volume=1_000.0 + i * 4,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("linear_regression_slope", {"period": 14, "source": "close"}),
        ("r_squared", {"period": 14, "source": "close"}),
        ("skewness", {"period": 30}),
        ("kurtosis", {"period": 30}),
        ("polynomial_regression_2", {"period": 30, "source": "close"}),
        ("polynomial_regression_3", {"period": 30, "source": "close"}),
        ("exponential_regression", {"period": 30, "source": "close"}),
        ("logarithmic_regression", {"period": 30, "source": "close"}),
        ("variance_ratio", {"short": 2, "long": 10}),
        ("autocorrelation", {"period": 30, "lag": 1}),
        ("spectral_dominant_period", {"window": 64, "source": "close"}),
        ("half_life_mean_reversion", {"period": 60, "source": "close"}),
    ],
)
def test_pack14_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 14 indicator dispatches successfully and produces
    a same-length series."""
    candles = _wavy_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    assert not any(f"{indicator_type}_inst" in w for w in warnings)
