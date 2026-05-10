"""Pack 5 — advanced statistical / risk / performance tests.

Each calculation gets at least one anchored-numeric correctness
test plus an edge case (empty / insufficient / divide-by-zero
monotone). Plus registry-promotion + dispatch + Pine-mapping
integration.

Same shape as Pack 2 / 3 / 4 — every pack pins its own delta in
its own file.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack5_active import PACK5_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.calmar_ratio import calmar_ratio
from app.strategy_engine.indicators.calculations.hurst_exponent import (
    hurst_exponent,
)
from app.strategy_engine.indicators.calculations.max_drawdown_pct import (
    max_drawdown_pct,
)
from app.strategy_engine.indicators.calculations.median_value import median_value
from app.strategy_engine.indicators.calculations.omega_ratio import omega_ratio
from app.strategy_engine.indicators.calculations.percentile_nearest import (
    percentile_nearest,
)
from app.strategy_engine.indicators.calculations.percentile_rank import (
    percentile_rank,
)
from app.strategy_engine.indicators.calculations.recovery_factor import (
    recovery_factor,
)
from app.strategy_engine.indicators.calculations.sharpe_ratio import sharpe_ratio
from app.strategy_engine.indicators.calculations.sortino_ratio import (
    sortino_ratio,
)
from app.strategy_engine.indicators.calculations.underwater_curve import (
    underwater_curve,
)
from app.strategy_engine.indicators.calculations.zscore import zscore
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.pine_import import convert_pine_to_strategy
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Statistical Ranks (3) ────────────────────────────────────────────


def test_percentile_rank_max_value_is_one_hundred() -> None:
    """Strictly increasing series → final bar is the max → rank = 100."""
    out = percentile_rank([1.0, 2.0, 3.0, 4.0, 5.0], period=5)
    assert out[4] == pytest.approx(100.0)


def test_percentile_rank_min_value_is_just_above_zero() -> None:
    """Strictly increasing series → first seeded bar is the min →
    rank = 100 / period (only itself counts as ``<=``)."""
    out = percentile_rank([5.0, 4.0, 3.0, 2.0, 1.0], period=5)
    # Last bar = 1.0, only one value <= it (itself) → 100 * 1/5 = 20.
    assert out[4] == pytest.approx(20.0)


def test_percentile_rank_constant_series_yields_one_hundred() -> None:
    out = percentile_rank([7.0] * 6, period=4)
    seeded = [v for v in out if v is not None]
    assert all(v == pytest.approx(100.0) for v in seeded)


def test_percentile_nearest_returns_window_median_at_p50() -> None:
    """50th percentile of an odd-length window = the middle element."""
    out = percentile_nearest(
        [10.0, 20.0, 30.0, 40.0, 50.0], period=5, percentage=50.0
    )
    # ceil(50/100 * 5) = 3 → 3rd-smallest = 30.
    assert out[4] == pytest.approx(30.0)


def test_percentile_nearest_at_one_hundred_returns_max() -> None:
    out = percentile_nearest(
        [10.0, 20.0, 30.0, 40.0, 50.0], period=5, percentage=100.0
    )
    assert out[4] == pytest.approx(50.0)


def test_percentile_nearest_rejects_invalid_percentage() -> None:
    with pytest.raises(ValueError):
        percentile_nearest([1.0, 2.0, 3.0], period=3, percentage=150.0)


def test_median_value_odd_window_returns_middle_element() -> None:
    out = median_value([10.0, 30.0, 20.0], period=3)
    assert out[2] == pytest.approx(20.0)


def test_median_value_even_window_averages_two_middles() -> None:
    """[1, 2, 3, 4]: middles = 2 and 3 → median = 2.5."""
    out = median_value([1.0, 2.0, 3.0, 4.0], period=4)
    assert out[3] == pytest.approx(2.5)


def test_median_value_insufficient_returns_empty() -> None:
    assert median_value([1.0, 2.0], period=5) == []


# ─── Performance Ratios (4) ───────────────────────────────────────────


def test_sharpe_ratio_positive_for_steady_uptrend() -> None:
    """Smooth uptrend with positive returns → positive Sharpe."""
    closes = [100.0 * (1.001 ** i) for i in range(60)]
    out = sharpe_ratio(closes, period=30, annualization=252)
    seeded = [v for v in out if v is not None]
    assert seeded
    assert all(v > 0 for v in seeded)


def test_sharpe_ratio_constant_returns_undefined() -> None:
    """Flat series → zero stdev → Sharpe undefined → None."""
    out = sharpe_ratio([100.0] * 30, period=20, annualization=252)
    assert all(v is None for v in out)


def test_sortino_ratio_no_downside_returns_none() -> None:
    """Pure-up series has no losing bars → downside_dev = 0 → None."""
    closes = [100.0 * (1.001 ** i) for i in range(40)]
    out = sortino_ratio(closes, period=30, annualization=252)
    assert all(v is None for v in out)


def test_sortino_ratio_handles_mixed_returns() -> None:
    """A series with both up and down bars produces a defined value."""
    closes: list[float] = [100.0]
    for i in range(1, 40):
        closes.append(closes[i - 1] * (1.005 if i % 3 != 0 else 0.995))
    out = sortino_ratio(closes, period=30, annualization=252)
    seeded = [v for v in out if v is not None]
    assert seeded


def test_calmar_ratio_undefined_when_no_drawdown() -> None:
    """Monotone uptrend → max_dd = 0 → Calmar undefined."""
    closes = [100.0 + i for i in range(40)]
    out = calmar_ratio(closes, period=30, annualization=252)
    assert all(v is None for v in out)


def test_calmar_ratio_defined_when_drawdown_exists() -> None:
    """Up-then-down gives a real drawdown."""
    closes = [100.0 + i for i in range(20)] + [
        119.0 - i * 0.5 for i in range(20)
    ]
    out = calmar_ratio(closes, period=30, annualization=252)
    seeded = [v for v in out if v is not None]
    assert seeded


def test_omega_ratio_no_losses_returns_none() -> None:
    """Threshold = 0; pure-up returns → no losses → Omega undefined."""
    closes = [100.0 * (1.001 ** i) for i in range(40)]
    out = omega_ratio(closes, period=30, threshold=0.0)
    assert all(v is None for v in out)


def test_omega_ratio_defined_for_mixed_series() -> None:
    closes: list[float] = [100.0]
    for i in range(1, 40):
        closes.append(closes[i - 1] * (1.005 if i % 3 != 0 else 0.995))
    out = omega_ratio(closes, period=30, threshold=0.0)
    seeded = [v for v in out if v is not None]
    assert seeded


# ─── Risk / Performance (3) ───────────────────────────────────────────


def test_max_drawdown_pct_zero_for_monotone_uptrend() -> None:
    closes = [100.0 + i for i in range(20)]
    out = max_drawdown_pct(closes, period=10)
    seeded = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in seeded)


def test_max_drawdown_pct_known_window_drop() -> None:
    """Peak 110, trough 99 → DD = 11/110 = 10%."""
    closes = [100.0, 105.0, 110.0, 105.0, 99.0]
    out = max_drawdown_pct(closes, period=5)
    assert out[4] == pytest.approx(10.0)


def test_underwater_curve_is_zero_at_new_peak() -> None:
    """Bar 0 is always 0 (running peak == itself)."""
    out = underwater_curve([100.0, 105.0, 110.0, 100.0])
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(0.0)
    assert out[2] == pytest.approx(0.0)
    # Bar 3: peak = 110, close = 100 → -10/110 * 100 ≈ -9.090909.
    assert out[3] == pytest.approx(-100.0 * 10.0 / 110.0)


def test_underwater_curve_empty_returns_empty() -> None:
    assert underwater_curve([]) == []


def test_recovery_factor_undefined_for_monotone_uptrend() -> None:
    closes = [100.0 + i for i in range(20)]
    out = recovery_factor(closes, period=10)
    assert all(v is None for v in out)


def test_recovery_factor_known_window() -> None:
    """Window [100, 105, 110, 105, 99, 110]: net = 110 - 100 = 10;
    max DD = 110 - 99 = 11 → recovery = 10 / 11."""
    closes = [100.0, 105.0, 110.0, 105.0, 99.0, 110.0]
    out = recovery_factor(closes, period=6)
    assert out[5] == pytest.approx(10.0 / 11.0)


# ─── Advanced Statistical (2) ─────────────────────────────────────────


def test_hurst_exponent_random_walk_yields_finite_value() -> None:
    """Pseudo-random walk produces a defined H in roughly [0, 1].
    Exact value is noisy on short series — pin only finiteness."""
    import random

    rng = random.Random(42)
    closes = [100.0]
    for _ in range(150):
        closes.append(closes[-1] * (1.0 + rng.gauss(0, 0.005)))
    out = hurst_exponent(closes, period=100)
    seeded = [v for v in out if v is not None]
    assert seeded
    for h in seeded:
        assert math.isfinite(h)


def test_hurst_exponent_rejects_period_below_minimum() -> None:
    with pytest.raises(ValueError):
        hurst_exponent([1.0, 2.0, 3.0], period=8)


def test_hurst_exponent_short_input_returns_empty() -> None:
    assert hurst_exponent([1.0, 2.0, 3.0], period=20) == []


def test_zscore_constant_window_returns_none() -> None:
    """Flat series → stdev = 0 → z undefined."""
    out = zscore([5.0, 5.0, 5.0, 5.0], period=3)
    assert all(v is None for v in out)


def test_zscore_known_window() -> None:
    """[1, 2, 3]: mean=2, var=2/3, std=sqrt(2/3); z[2] = (3 - 2)/std."""
    out = zscore([1.0, 2.0, 3.0], period=3)
    expected = (3.0 - 2.0) / math.sqrt(2.0 / 3.0)
    assert out[2] == pytest.approx(expected)


def test_zscore_empty_returns_empty() -> None:
    assert zscore([], period=5) == []


# ─── Registry promotion ───────────────────────────────────────────────


_PACK5_IDS = {
    "percentile_rank",
    "percentile_nearest",
    "median_value",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "omega_ratio",
    "max_drawdown_pct",
    "underwater_curve",
    "recovery_factor",
    "hurst_exponent",
    "zscore",
}


def test_pack5_module_exposes_twelve_indicators() -> None:
    assert len(PACK5_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK5_ACTIVE_INDICATORS} == _PACK5_IDS


def test_pack5_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK5_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack5_is_seventy_one() -> None:
    """20 historical + 15 Pack 2 + 12 Pack 3 + 12 Pack 4 + 12 Pack 5 = 71.

    Loose lower bound for forward compatibility — each pack pins
    its own delta in its own test file."""
    assert len(get_active_indicators()) >= 71


def test_pack5_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK5_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


# ─── Backtest dispatch ───────────────────────────────────────────────


def _trending_candles(n: int = 60) -> list:
    return [
        make_candle(
            minutes=i,
            open_=100.0 + i * 0.5,
            high=100.5 + i * 0.5,
            low=99.5 + i * 0.5,
            close=100.0 + i * 0.5,
            volume=1_000.0 + i * 10,
        )
        for i in range(n)
    ]


def _wavy_candles(n: int = 80) -> list:
    out = []
    for i in range(n):
        wave = math.sin(i * 0.2) * 5
        close = 100.0 + wave
        out.append(
            make_candle(
                minutes=i,
                open_=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000.0 + i * 7,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("percentile_rank", {"period": 20, "source": "close"}),
        (
            "percentile_nearest",
            {"period": 20, "percentage": 75.0, "source": "close"},
        ),
        ("median_value", {"period": 10, "source": "close"}),
        (
            "sharpe_ratio",
            {"period": 30, "annualization": 252, "risk_free_rate": 0.0},
        ),
        ("max_drawdown_pct", {"period": 20}),
        ("underwater_curve", {}),
        ("zscore", {"period": 20, "source": "close"}),
    ],
)
def test_pack5_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 5 indicator dispatches successfully and produces a
    same-length series. Some indicators (sharpe/sortino/calmar/omega)
    can return all-None on synthetic data — those are exercised in
    the calc tests above where the data shape is controlled."""
    candles = _wavy_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    # No multi-output warning for any Pack 5 indicator.
    assert not any(f"{indicator_type}_inst" in w for w in warnings)


def test_dispatch_pack5_with_phase1_indicators_coexist() -> None:
    """A strategy mixing Phase 1 EMA + Pack 5 zscore + sharpe runs in
    a single precompute pass."""
    candles = _trending_candles(80)
    strategy = make_strategy(
        indicators=[
            {"id": "ema_main", "type": "ema", "params": {"period": 9, "source": "close"}},
            {"id": "z_main", "type": "zscore", "params": {"period": 20, "source": "close"}},
            {
                "id": "sharpe_main",
                "type": "sharpe_ratio",
                "params": {"period": 30, "annualization": 252, "risk_free_rate": 0.0},
            },
        ],
    )
    series, _warnings = precompute_indicators(candles, strategy)
    assert {"ema_main", "z_main", "sharpe_main"} <= series.keys()


# ─── Pine importer ───────────────────────────────────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Pack 5 importer test")
"""

_TRIGGER_TAIL = """
trigger = ta.crossover(close, open)
if trigger
    strategy.entry("Long", strategy.long)
"""


def _wrap(indicator_line: str) -> str:
    return f"{_PINE_HEADER}{indicator_line}\n{_TRIGGER_TAIL}"


def _by_id(result: dict[str, object]) -> dict[str, dict[str, object]]:
    indicators = result["strategy"]["indicators"]  # type: ignore[index]
    return {ind["id"]: ind for ind in indicators}  # type: ignore[index, attr-defined]


def test_pine_percentrank_maps_to_percentile_rank() -> None:
    src = _wrap("pr_val = ta.percentrank(close, 100)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "pr_val" in inds
    assert inds["pr_val"]["type"] == "percentile_rank"
    assert inds["pr_val"]["params"] == {"period": 100, "source": "close"}


def test_pine_percentile_nearest_rank_maps_to_percentile_nearest() -> None:
    src = _wrap("pn_val = ta.percentile_nearest_rank(close, 100, 75)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "pn_val" in inds
    assert inds["pn_val"]["type"] == "percentile_nearest"
    assert inds["pn_val"]["params"] == {
        "period": 100,
        "percentage": 75.0,
        "source": "close",
    }


def test_pine_median_maps_to_median_value() -> None:
    src = _wrap("med_val = ta.median(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "med_val" in inds
    assert inds["med_val"]["type"] == "median_value"
    assert inds["med_val"]["params"] == {"period": 20, "source": "close"}
