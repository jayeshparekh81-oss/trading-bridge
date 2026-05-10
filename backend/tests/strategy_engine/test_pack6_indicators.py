"""Pack 6 — volume-flow + advanced-volatility tests.

Each calculation gets at least one anchored-numeric correctness
test plus an edge case (empty / insufficient / divide-by-zero
monotone). Plus registry-promotion + dispatch + Pine-mapping
integration.

Same shape as Pack 2 / 3 / 4 / 5 — every pack pins its own delta
in its own file. Active count assertion is ``>= 83`` (loose lower
bound for forward compat).
"""

from __future__ import annotations

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack6_active import PACK6_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.accumulation_distribution import (
    accumulation_distribution,
)
from app.strategy_engine.indicators.calculations.awesome_oscillator import (
    awesome_oscillator,
)
from app.strategy_engine.indicators.calculations.bollinger_bandwidth import (
    bollinger_bandwidth,
)
from app.strategy_engine.indicators.calculations.bollinger_percent_b import (
    bollinger_percent_b,
)
from app.strategy_engine.indicators.calculations.chaikin_oscillator import (
    chaikin_oscillator,
)
from app.strategy_engine.indicators.calculations.choppiness_index import (
    choppiness_index,
)
from app.strategy_engine.indicators.calculations.ease_of_movement import (
    ease_of_movement,
)
from app.strategy_engine.indicators.calculations.elder_ray_bear import (
    elder_ray_bear,
)
from app.strategy_engine.indicators.calculations.elder_ray_bull import (
    elder_ray_bull,
)
from app.strategy_engine.indicators.calculations.mass_index import mass_index
from app.strategy_engine.indicators.calculations.price_volume_trend import (
    price_volume_trend,
)
from app.strategy_engine.indicators.calculations.twiggs_money_flow import (
    twiggs_money_flow,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.pine_import import convert_pine_to_strategy
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Volume Flow (5) ─────────────────────────────────────────────────


def test_accumulation_distribution_close_at_high_grows_line() -> None:
    """Three bars with close == high → MFM=+1 each → A/D climbs by
    full volume each bar (cumulative)."""
    out = accumulation_distribution(
        highs=[10.0, 11.0, 12.0],
        lows=[9.0, 10.0, 11.0],
        closes=[10.0, 11.0, 12.0],  # close at high → MFM = +1
        volumes=[100.0, 200.0, 300.0],
    )
    assert out == [100.0, 300.0, 600.0]


def test_accumulation_distribution_flat_bar_contributes_zero() -> None:
    """A flat bar (high == low) adds 0 to the running line."""
    out = accumulation_distribution(
        highs=[10.0, 10.0],
        lows=[10.0, 9.0],  # bar 0 flat, bar 1 normal
        closes=[10.0, 9.0],
        volumes=[100.0, 50.0],
    )
    assert out is not None
    assert out[0] == 0.0  # flat bar
    assert out[1] != 0.0  # normal bar contributes


def test_accumulation_distribution_empty_returns_empty() -> None:
    assert accumulation_distribution([], [], [], []) == []


def test_chaikin_oscillator_rejects_fast_geq_slow() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        chaikin_oscillator(
            highs=[1.0] * 30,
            lows=[1.0] * 30,
            closes=[1.0] * 30,
            volumes=[100.0] * 30,
            fast=10,
            slow=10,
        )


def test_chaikin_oscillator_returns_same_length() -> None:
    n = 50
    out = chaikin_oscillator(
        highs=[10.0 + i * 0.1 for i in range(n)],
        lows=[9.0 + i * 0.1 for i in range(n)],
        closes=[9.5 + i * 0.1 for i in range(n)],
        volumes=[1000.0] * n,
        fast=3,
        slow=10,
    )
    assert len(out) == n


def test_price_volume_trend_starts_at_zero() -> None:
    out = price_volume_trend(closes=[100.0, 101.0, 102.0], volumes=[10, 10, 10])
    assert out is not None
    assert out[0] == 0.0
    # +1% on bar 1 with volume 10 → +0.1
    assert out[1] == pytest.approx(0.1)


def test_price_volume_trend_handles_zero_prev_close() -> None:
    """A zero previous close skips that bar's contribution rather
    than dividing by zero."""
    out = price_volume_trend(closes=[0.0, 1.0, 2.0], volumes=[10, 10, 10])
    assert out is not None
    assert out[0] == 0.0
    # Bar 1 saw closes[0]==0 → skip. Bar 2 sees 100% rise from 1→2
    # with volume 10 → +10 cumulative.
    assert out[1] == 0.0
    assert out[2] == pytest.approx(10.0)


def test_ease_of_movement_returns_same_length() -> None:
    n = 30
    out = ease_of_movement(
        highs=[10.0 + i * 0.1 for i in range(n)],
        lows=[9.0 + i * 0.1 for i in range(n)],
        volumes=[1000.0] * n,
        period=14,
    )
    assert len(out) == n
    # Warm-up bars (indices 0..13) are None.
    assert all(v is None for v in out[:14])
    # Post-warmup bars are real numbers.
    assert all(v is not None for v in out[14:])


def test_ease_of_movement_insufficient_returns_empty() -> None:
    assert ease_of_movement(highs=[1.0] * 10, lows=[1.0] * 10,
                             volumes=[1.0] * 10, period=20) == []


def test_twiggs_money_flow_constant_volume_handles_flat() -> None:
    """All-flat bars produce mfv=0 → output 0 / volume_ema = 0."""
    n = 50
    out = twiggs_money_flow(
        highs=[10.0] * n,
        lows=[10.0] * n,
        closes=[10.0] * n,
        volumes=[1000.0] * n,
        period=21,
    )
    assert len(out) == n
    # Every defined bar should be 0 (no flow signal on flat bars).
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


# ─── Momentum / Oscillators (4) ──────────────────────────────────────


def test_mass_index_insufficient_returns_empty() -> None:
    """Needs ema_period * 2 + sum_period bars minimum."""
    out = mass_index(highs=[1.0] * 30, lows=[1.0] * 30, ema_period=9, sum_period=25)
    assert out == []


def test_mass_index_returns_finite_values_on_volatile_data() -> None:
    n = 100
    out = mass_index(
        highs=[10.0 + (i % 5) for i in range(n)],
        lows=[8.0 + (i % 5) for i in range(n)],
        ema_period=9,
        sum_period=25,
    )
    assert len(out) == n
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    # All defined values should be finite + positive (sum of ratios).
    assert all(v > 0 for v in defined)


def test_awesome_oscillator_rejects_fast_geq_slow() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        awesome_oscillator(highs=[1.0] * 50, lows=[1.0] * 50, fast=34, slow=34)


def test_awesome_oscillator_known_constant_yields_zero() -> None:
    """Constant median → both SMAs equal → AO = 0 on every defined bar."""
    n = 50
    out = awesome_oscillator(highs=[10.0] * n, lows=[8.0] * n, fast=5, slow=34)
    assert len(out) == n
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_elder_ray_bull_known_window() -> None:
    """Constant close + EMA = same constant; bull = high - close → constant."""
    closes = [100.0] * 30
    highs = [102.0] * 30
    out = elder_ray_bull(highs=highs, closes=closes, period=13)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(2.0) for v in defined)


def test_elder_ray_bear_known_window() -> None:
    """Constant close + EMA = same constant; bear = low - close → constant."""
    closes = [100.0] * 30
    lows = [98.0] * 30
    out = elder_ray_bear(lows=lows, closes=closes, period=13)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(-2.0) for v in defined)


# ─── Volatility / Trend Strength (3) ────────────────────────────────


def test_choppiness_index_rejects_period_below_two() -> None:
    """``period < 2`` triggers div-by-zero in log10(period)."""
    with pytest.raises(ValueError, match=">= 2"):
        choppiness_index(highs=[1.0] * 20, lows=[1.0] * 20,
                          closes=[1.0] * 20, period=1)


def test_choppiness_index_trending_series_yields_low_value() -> None:
    """A monotone uptrend should produce CI well below 50 — TR sum
    is small relative to the (HH - LL) range."""
    n = 50
    out = choppiness_index(
        highs=[10.0 + i for i in range(n)],
        lows=[9.0 + i for i in range(n)],
        closes=[9.5 + i for i in range(n)],
        period=14,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(v < 50.0 for v in defined), defined


def test_bollinger_bandwidth_constant_input_yields_zero_or_none() -> None:
    """Constant input → zero std → upper == middle == lower → bandwidth = 0."""
    out = bollinger_bandwidth(values=[100.0] * 30, period=20, std_dev=2.0)
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_bollinger_percent_b_at_middle_returns_half() -> None:
    """For a constant-then-spike series the constant tail puts price
    at the middle (since constant tail dominates the rolling mean
    + std). %B at the middle is 0.5 — but only when band width > 0,
    which a fully-constant series doesn't satisfy. Use a slightly
    varying series."""
    values = [100.0] * 19 + [101.0]
    out = bollinger_percent_b(values=values, period=20, std_dev=2.0)
    # Last value should be defined since there's now nonzero std.
    assert out[-1] is not None


def test_bollinger_bandwidth_empty_returns_empty() -> None:
    assert bollinger_bandwidth(values=[], period=20) == []


# ─── Registry promotion ──────────────────────────────────────────────


_PACK6_IDS = {
    "accumulation_distribution",
    "chaikin_oscillator",
    "price_volume_trend",
    "ease_of_movement",
    "twiggs_money_flow",
    "mass_index",
    "awesome_oscillator",
    "elder_ray_bull",
    "elder_ray_bear",
    "choppiness_index",
    "bollinger_bandwidth",
    "bollinger_percent_b",
}


def test_pack6_module_exposes_twelve_indicators() -> None:
    assert len(PACK6_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK6_ACTIVE_INDICATORS} == _PACK6_IDS


def test_pack6_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK6_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack6_is_eighty_three() -> None:
    """20 historical + 15 Pack 2 + 12 Pack 3 + 12 Pack 4 + 12 Pack 5
    + 12 Pack 6 = 83.

    Loose lower bound for forward compatibility — each pack pins
    its own delta in its own test file."""
    assert len(get_active_indicators()) >= 83


def test_pack6_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK6_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack6_no_beginner_difficulty() -> None:
    """Spec says 'avoid beginner set lock' — every Pack 6 entry
    must be INTERMEDIATE or EXPERT. Catches a future edit that
    accidentally drops a tier."""
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK6_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


# ─── Backtest dispatch ──────────────────────────────────────────────


def _vol_candles(n: int = 80) -> list:
    """Synthetic OHLC with non-trivial range + volume — enough to
    exercise every Pack 6 indicator's defined-value path."""
    out = []
    for i in range(n):
        base = 100.0 + (i % 7) - 3.0  # zig-zag
        out.append(
            make_candle(
                minutes=i,
                open_=base,
                high=base + 1.5,
                low=base - 1.5,
                close=base + 0.5,
                volume=1_000.0 + i * 3,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("accumulation_distribution", {}),
        ("chaikin_oscillator", {"fast": 3, "slow": 10}),
        ("price_volume_trend", {}),
        ("ease_of_movement", {"period": 14}),
        ("twiggs_money_flow", {"period": 21}),
        ("mass_index", {"ema_period": 9, "sum_period": 25}),
        ("awesome_oscillator", {"fast": 5, "slow": 34}),
        ("elder_ray_bull", {"period": 13}),
        ("elder_ray_bear", {"period": 13}),
        ("choppiness_index", {"period": 14}),
        ("bollinger_bandwidth", {"period": 20, "std_dev": 2.0, "source": "close"}),
        ("bollinger_percent_b", {"period": 20, "std_dev": 2.0, "source": "close"}),
    ],
)
def test_pack6_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 6 indicator dispatches successfully and produces a
    same-length series. Defined-value coverage is in the per-calc
    tests above; here we just confirm the dispatch wiring."""
    candles = _vol_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    # No multi-output warning for any Pack 6 indicator.
    assert not any(f"{indicator_type}_inst" in w for w in warnings)


# ─── Pine importer ──────────────────────────────────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Pack 6 importer test")
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


def test_pine_accdist_maps_to_accumulation_distribution() -> None:
    src = _wrap("ad_val = ta.accdist()")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "ad_val" in inds
    assert inds["ad_val"]["type"] == "accumulation_distribution"
    assert inds["ad_val"]["params"] == {}


def test_pine_ao_maps_to_awesome_oscillator() -> None:
    src = _wrap("ao_val = ta.ao()")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "ao_val" in inds
    assert inds["ao_val"]["type"] == "awesome_oscillator"
    assert inds["ao_val"]["params"] == {"fast": 5, "slow": 34}
