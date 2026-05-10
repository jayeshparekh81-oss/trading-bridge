"""Pack 4 — S/R + statistical + volatility/range tests.

Each calculation gets at least one anchored-numeric correctness
test plus an edge case (empty / insufficient / divide-by-zero).
Plus registry-promotion + dispatch + Pine-mapping integration.

Pattern matches Pack 2 / Pack 3 — every pack pins its own delta
in its own file.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack4_active import PACK4_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.camarilla_pivots import (
    camarilla_pivots,
)
from app.strategy_engine.indicators.calculations.correlation_coefficient import (
    correlation_coefficient,
)
from app.strategy_engine.indicators.calculations.high_low_spread import (
    high_low_spread,
)
from app.strategy_engine.indicators.calculations.historical_volatility import (
    historical_volatility,
)
from app.strategy_engine.indicators.calculations.inside_bar import inside_bar
from app.strategy_engine.indicators.calculations.regression_channel import (
    regression_channel,
)
from app.strategy_engine.indicators.calculations.std_dev import std_dev
from app.strategy_engine.indicators.calculations.swing_high import swing_high
from app.strategy_engine.indicators.calculations.swing_low import swing_low
from app.strategy_engine.indicators.calculations.true_range import true_range
from app.strategy_engine.indicators.calculations.variance import variance
from app.strategy_engine.indicators.calculations.woodie_pivots import (
    woodie_pivots,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.pine_import import convert_pine_to_strategy
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Statistical (4) ─────────────────────────────────────────────────


def test_std_dev_known_three_value_window() -> None:
    """3-bar window of [1, 2, 3]: mean=2, var = (1+0+1)/3 = 2/3,
    stdev = sqrt(2/3)."""
    out = std_dev([1.0, 2.0, 3.0], period=3)
    assert out[0] is None and out[1] is None
    assert out[2] == pytest.approx(math.sqrt(2.0 / 3.0))


def test_std_dev_constant_series_yields_zero() -> None:
    out = std_dev([5.0, 5.0, 5.0, 5.0, 5.0], period=3)
    for v in out[2:]:
        assert v == pytest.approx(0.0)


def test_std_dev_insufficient_input_returns_empty() -> None:
    assert std_dev([1.0, 2.0], period=5) == []


def test_variance_is_std_dev_squared() -> None:
    """Population variance — ``std_dev ** 2`` per the population
    formula match."""
    values = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
    var_out = variance(values, period=4)
    std_out = std_dev(values, period=4)
    for v, s in zip(var_out, std_out, strict=True):
        if v is None or s is None:
            continue
        assert v == pytest.approx(s ** 2)


def test_correlation_coefficient_perfect_positive_is_one() -> None:
    """y = x → correlation = +1."""
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [10.0, 20.0, 30.0, 40.0, 50.0]
    out = correlation_coefficient(a, b, period=5)
    assert out[4] == pytest.approx(1.0)


def test_correlation_coefficient_perfect_negative_is_minus_one() -> None:
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [50.0, 40.0, 30.0, 20.0, 10.0]
    out = correlation_coefficient(a, b, period=5)
    assert out[4] == pytest.approx(-1.0)


def test_correlation_coefficient_flat_series_returns_none() -> None:
    """One series flat → stdev_b = 0 → correlation undefined."""
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [10.0, 10.0, 10.0, 10.0, 10.0]
    out = correlation_coefficient(a, b, period=5)
    assert out[4] is None


def test_correlation_coefficient_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        correlation_coefficient([1.0, 2.0], [1.0], period=2)


def test_historical_volatility_constant_series_is_zero() -> None:
    """log(c/c) = 0 for a flat series → HV is 0."""
    out = historical_volatility([100.0] * 25, period=20, annualization=252)
    seeded = [v for v in out if v is not None]
    assert seeded
    assert all(v == pytest.approx(0.0) for v in seeded)


def test_historical_volatility_handles_short_input() -> None:
    """``period >= len(closes)`` → empty (no return-series window)."""
    assert historical_volatility([100.0, 101.0], period=10) == []


# ─── Volatility / Range (3) ──────────────────────────────────────────


def test_true_range_first_bar_is_just_high_minus_low() -> None:
    """No prior close → TR[0] is ``high[0] - low[0]``."""
    out = true_range([10.0, 12.0], [9.0, 11.0], [9.5, 11.5])
    assert out[0] == pytest.approx(1.0)


def test_true_range_uses_prior_close_when_it_extends_the_range() -> None:
    """Bar 1 high=12, low=11, prev_close=8 → TR = max(1, 4, 3) = 4."""
    out = true_range([10.0, 12.0], [9.0, 11.0], [8.0, 11.5])
    assert out[1] == pytest.approx(4.0)


def test_true_range_empty_returns_empty() -> None:
    assert true_range([], [], []) == []


def test_high_low_spread_returns_percent_of_close() -> None:
    """(102 - 98) / 100 * 100 = 4.0 %."""
    out = high_low_spread([102.0], [98.0], [100.0])
    assert out[0] == pytest.approx(4.0)


def test_high_low_spread_zero_close_returns_none() -> None:
    out = high_low_spread([1.0, 2.0], [0.5, 1.5], [0.0, 1.0])
    assert out[0] is None
    assert out[1] == pytest.approx(0.5 / 1.0 * 100.0)


def test_inside_bar_detects_contained_range() -> None:
    """Bar 1 high <= bar 0 high AND bar 1 low >= bar 0 low."""
    out = inside_bar([100.0, 99.5], [98.0, 98.5])
    assert out == [None, 1.0]


def test_inside_bar_skips_when_not_contained() -> None:
    out = inside_bar([100.0, 101.0], [98.0, 97.5])
    assert out == [None, 0.0]


# ─── Support / Resistance (5) ────────────────────────────────────────


def test_swing_high_detects_pivot_at_right_bars_delay() -> None:
    """Pivot at index 2 with left=2/right=2 → confirmed at index 4."""
    highs = [10.0, 11.0, 15.0, 12.0, 11.5, 10.5]
    out = swing_high(highs, left_bars=2, right_bars=2)
    # Pivot at idx 2, confirm at idx 2 + right_bars = 4.
    assert out[4] == pytest.approx(15.0)
    # Bars before the confirmation window are None.
    assert all(v is None for v in out[:4])


def test_swing_high_no_pivot_when_high_is_not_window_max() -> None:
    """Steady uptrend → pivot is always the most-recent bar inside the
    look-ahead window, but the pivot bar itself isn't a window max."""
    out = swing_high([10.0, 11.0, 12.0, 13.0, 14.0, 15.0], left_bars=2, right_bars=2)
    assert all(v is None for v in out)


def test_swing_low_detects_pivot_at_right_bars_delay() -> None:
    lows = [12.0, 11.0, 8.0, 11.0, 11.5, 12.5]
    out = swing_low(lows, left_bars=2, right_bars=2)
    assert out[4] == pytest.approx(8.0)


def test_swing_low_empty_returns_empty() -> None:
    assert swing_low([], left_bars=2, right_bars=2) == []


def test_camarilla_pivots_first_bar_is_none_for_every_level() -> None:
    """No prior bar → every level None at index 0."""
    r3, r4, s3, s4 = camarilla_pivots([10.0], [9.0], [9.5])
    assert r3 == [None] and r4 == [None] and s3 == [None] and s4 == [None]


def test_camarilla_pivots_levels_ordered_correctly() -> None:
    """For range = 4, close = 100:
        R4 = 100 + 4 * 1.1 / 2 = 102.2
        R3 = 100 + 4 * 1.1 / 4 = 101.1
        S3 = 100 - 1.1 = 98.9
        S4 = 100 - 2.2 = 97.8
    """
    highs = [102.0, 105.0]
    lows = [98.0, 103.0]
    closes = [100.0, 104.0]
    r3, r4, s3, s4 = camarilla_pivots(highs, lows, closes)
    assert r4[1] == pytest.approx(102.2)
    assert r3[1] == pytest.approx(101.1)
    assert s3[1] == pytest.approx(98.9)
    assert s4[1] == pytest.approx(97.8)


def test_woodie_pivots_pp_is_close_weighted() -> None:
    """PP = (H + L + 2C) / 4. For H=102, L=98, C=100 → PP = 100."""
    highs = [102.0, 105.0]
    lows = [98.0, 103.0]
    closes = [100.0, 104.0]
    pp, r1, r2, s1, s2 = woodie_pivots(highs, lows, closes)
    assert pp[1] == pytest.approx(100.0)
    # R1 = 2 * 100 - 98 = 102; S1 = 2 * 100 - 102 = 98.
    assert r1[1] == pytest.approx(102.0)
    assert s1[1] == pytest.approx(98.0)
    # R2 = PP + range = 100 + 4 = 104; S2 = 100 - 4 = 96.
    assert r2[1] == pytest.approx(104.0)
    assert s2[1] == pytest.approx(96.0)


def test_regression_channel_constant_series_yields_flat_bands() -> None:
    """On a flat series, regression line = constant and residuals = 0
    → upper = middle = lower."""
    values = [50.0] * 30
    middle, upper, lower = regression_channel(values, period=20, std_dev=2.0)
    seeded = [
        (m, u, lo)
        for m, u, lo in zip(middle, upper, lower, strict=True)
        if m is not None
    ]
    assert seeded
    for m, u, lo in seeded:
        assert m == pytest.approx(50.0)
        assert u == pytest.approx(m)
        assert lo == pytest.approx(m)


def test_regression_channel_band_geometry_is_symmetric() -> None:
    """For any seeded bar the upper-to-middle gap equals the
    middle-to-lower gap."""
    values = [100.0 + i for i in range(30)]
    middle, upper, lower = regression_channel(values, period=10, std_dev=2.0)
    seeded = [
        (m, u, lo)
        for m, u, lo in zip(middle, upper, lower, strict=True)
        if m is not None and u is not None and lo is not None
    ]
    assert seeded
    for m, u, lo in seeded:
        assert (u - m) == pytest.approx(m - lo)


def test_regression_channel_rejects_period_below_two() -> None:
    with pytest.raises(ValueError):
        regression_channel([1.0, 2.0, 3.0], period=1)


# ─── Registry promotion ──────────────────────────────────────────────


_PACK4_IDS = {
    "camarilla_pivots",
    "woodie_pivots",
    "swing_high",
    "swing_low",
    "regression_channel",
    "std_dev",
    "variance",
    "correlation_coefficient",
    "historical_volatility",
    "true_range",
    "high_low_spread",
    "inside_bar",
}


def test_pack4_module_exposes_twelve_indicators() -> None:
    assert len(PACK4_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK4_ACTIVE_INDICATORS} == _PACK4_IDS


def test_pack4_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK4_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack4_is_fifty_nine() -> None:
    """20 historical + 15 Pack 2 + 12 Pack 3 + 12 Pack 4 = 59.

    Loose lower bound for forward compatibility — each pack pins
    its own delta in its own test file."""
    assert len(get_active_indicators()) >= 59


def test_pack4_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK4_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


# ─── Backtest dispatch ───────────────────────────────────────────────


def _trending_candles(n: int = 40) -> list:
    return [
        make_candle(
            minutes=i,
            open_=100.0 + i,
            high=100.5 + i,
            low=99.5 + i,
            close=100.0 + i,
            volume=1_000.0 + i * 10,
        )
        for i in range(n)
    ]


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("std_dev", {"period": 5, "source": "close"}),
        ("variance", {"period": 5, "source": "close"}),
        (
            "correlation_coefficient",
            {"period": 5, "source_a": "close", "source_b": "open"},
        ),
        ("historical_volatility", {"period": 10, "annualization": 252}),
        ("true_range", {}),
        ("high_low_spread", {}),
        ("inside_bar", {}),
        ("swing_high", {"left_bars": 3, "right_bars": 3}),
        ("swing_low", {"left_bars": 3, "right_bars": 3}),
    ],
)
def test_pack4_single_output_indicators_dispatch(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each single-output Pack 4 indicator runs through the
    dispatcher and produces a populated series."""
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    # No multi-output warning for single-line indicators.
    assert not any(f"{indicator_type}_inst" in w for w in warnings)


def test_camarilla_pivots_dispatches_with_four_extras() -> None:
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {"id": "cam", "type": "camarilla_pivots", "params": {}},
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    assert {"cam", "cam.r3", "cam.r4", "cam.s3", "cam.s4"} <= series.keys()
    # Geometry: r4 > r3 > close > s3 > s4 once seeded.
    for i in range(1, len(candles)):
        r3, r4, s3, s4 = (
            series["cam.r3"][i],
            series["cam.r4"][i],
            series["cam.s3"][i],
            series["cam.s4"][i],
        )
        if any(v is None for v in (r3, r4, s3, s4)):
            continue
        assert r4 > r3 > s3 > s4
    assert any("cam" in w and "multi-output" in w for w in warnings)


def test_woodie_pivots_dispatches_with_five_extras() -> None:
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {"id": "woodie", "type": "woodie_pivots", "params": {}},
        ],
    )
    series, _warnings = precompute_indicators(candles, strategy)
    assert {
        "woodie",
        "woodie.pp",
        "woodie.r1",
        "woodie.r2",
        "woodie.s1",
        "woodie.s2",
    } <= series.keys()


def test_regression_channel_dispatches_with_three_extras() -> None:
    candles = _trending_candles()
    strategy = make_strategy(
        indicators=[
            {
                "id": "rc",
                "type": "regression_channel",
                "params": {"period": 10, "std_dev": 2.0, "source": "close"},
            },
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    assert {"rc", "rc.middle", "rc.upper", "rc.lower"} <= series.keys()
    assert any("rc" in w and "multi-output" in w for w in warnings)


# ─── Pine importer ───────────────────────────────────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Pack 4 importer test")
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


def test_pine_pivothigh_maps_to_swing_high() -> None:
    src = _wrap("ph_val = ta.pivothigh(5, 5)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "ph_val" in inds
    assert inds["ph_val"]["type"] == "swing_high"
    assert inds["ph_val"]["params"] == {"left_bars": 5, "right_bars": 5}


def test_pine_pivotlow_maps_to_swing_low() -> None:
    src = _wrap("pl_val = ta.pivotlow(3, 3)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "pl_val" in inds
    assert inds["pl_val"]["type"] == "swing_low"
    assert inds["pl_val"]["params"] == {"left_bars": 3, "right_bars": 3}


def test_pine_stdev_maps_to_std_dev() -> None:
    src = _wrap("sd_val = ta.stdev(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "sd_val" in inds
    assert inds["sd_val"]["type"] == "std_dev"
    assert inds["sd_val"]["params"] == {"period": 20, "source": "close"}


def test_pine_variance_maps_to_variance() -> None:
    src = _wrap("var_val = ta.variance(close, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "var_val" in inds
    assert inds["var_val"]["type"] == "variance"
    assert inds["var_val"]["params"] == {"period": 20, "source": "close"}


def test_pine_correlation_maps_to_correlation_coefficient() -> None:
    src = _wrap("corr_val = ta.correlation(close, open, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "corr_val" in inds
    assert inds["corr_val"]["type"] == "correlation_coefficient"
    assert inds["corr_val"]["params"] == {
        "period": 20,
        "source_a": "close",
        "source_b": "open",
    }
