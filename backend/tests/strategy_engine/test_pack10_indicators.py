"""Pack 10 — volume profile + microstructure + order flow tests.

Same shape as Pack 2-9. Active count assertion ``>= 131``.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack10_active import (
    PACK10_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.buying_pressure_ratio import (
    buying_pressure_ratio,
)
from app.strategy_engine.indicators.calculations.cumulative_volume_delta import (
    cumulative_volume_delta,
)
from app.strategy_engine.indicators.calculations.money_flow_ratio import (
    money_flow_ratio,
)
from app.strategy_engine.indicators.calculations.negative_volume_index import (
    negative_volume_index,
)
from app.strategy_engine.indicators.calculations.on_balance_volume_ema import (
    on_balance_volume_ema,
)
from app.strategy_engine.indicators.calculations.percent_price_oscillator import (
    percent_price_oscillator,
)
from app.strategy_engine.indicators.calculations.positive_volume_index import (
    positive_volume_index,
)
from app.strategy_engine.indicators.calculations.rate_of_change_volume import (
    rate_of_change_volume,
)
from app.strategy_engine.indicators.calculations.true_strength_index import (
    true_strength_index,
)
from app.strategy_engine.indicators.calculations.volume_at_price_high import (
    volume_at_price_high,
)
from app.strategy_engine.indicators.calculations.volume_breakout import (
    volume_breakout,
)
from app.strategy_engine.indicators.calculations.volume_weighted_avg_close import (
    volume_weighted_avg_close,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.pine_import import convert_pine_to_strategy
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Volume Profile (4) ──────────────────────────────────────────────


def test_vwac_constant_input_returns_constant() -> None:
    out = volume_weighted_avg_close(
        closes=[100.0] * 30, volumes=[100.0] * 30, period=14
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(100.0) for v in defined)


def test_vwac_zero_volume_window_returns_none() -> None:
    out = volume_weighted_avg_close(
        closes=[100.0] * 5, volumes=[0.0] * 5, period=3
    )
    # All defined entries should be None (zero-volume window).
    assert all(v is None for v in out)


def test_volume_at_price_high_flat_window_returns_flat_price() -> None:
    """When prices are flat the POC degenerates to the flat price."""
    out = volume_at_price_high(
        closes=[100.0] * 30, volumes=[1.0] * 30, period=10, bins=10
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(100.0) for v in defined)


def test_volume_at_price_high_emits_high_volume_bucket() -> None:
    """Construct a window where price 105 has the most volume; POC
    should land near 105."""
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 105.0, 105.0,
               105.0, 105.0, 100.0]
    volumes = [1.0] * 10 + [1.0]
    out = volume_at_price_high(
        closes=closes, volumes=volumes, period=10, bins=5
    )
    last = out[-1]
    assert last is not None
    # Bin centres for [100..105] in 5 bins → 100.5, 101.5, 102.5,
    # 103.5, 104.5. The 5x105 cluster lands in the highest bin →
    # POC ≈ 104.5.
    assert last == pytest.approx(104.5, abs=1.0)


def test_volume_breakout_spike_on_bull_bar_yields_plus_one() -> None:
    """Last bar volume >> avg with close > open → +1."""
    opens = [100.0] * 20 + [100.0]
    closes = [100.0] * 20 + [101.0]
    volumes = [10.0] * 20 + [50.0]  # 5x avg
    out = volume_breakout(opens, closes, volumes, period=20, spike_mult=2.0)
    assert out[-1] == 1.0


def test_volume_breakout_spike_on_bear_bar_yields_minus_one() -> None:
    opens = [100.0] * 20 + [100.0]
    closes = [100.0] * 20 + [99.0]
    volumes = [10.0] * 20 + [50.0]
    out = volume_breakout(opens, closes, volumes, period=20, spike_mult=2.0)
    assert out[-1] == -1.0


def test_volume_breakout_no_spike_yields_zero() -> None:
    out = volume_breakout(
        opens=[100.0] * 21, closes=[100.5] * 21, volumes=[10.0] * 21,
        period=20, spike_mult=2.0,
    )
    assert out[-1] == 0.0


def test_pvi_seeds_at_thousand() -> None:
    out = positive_volume_index(closes=[100.0] * 5, volumes=[1.0] * 5)
    assert out[0] == 1000.0


def test_pvi_only_updates_on_volume_up_days() -> None:
    """Bar 1: vol up + price up → PVI should rise.
    Bar 2: vol down → PVI unchanged."""
    closes = [100.0, 110.0, 120.0]
    volumes = [10.0, 20.0, 5.0]  # bar 1 vol up; bar 2 vol down
    out = positive_volume_index(closes=closes, volumes=volumes)
    assert out[0] == 1000.0
    assert out[1] == pytest.approx(1100.0)  # 1000 + 1000 * 0.10
    assert out[2] == out[1]  # bar 2 vol-down → unchanged


# ─── Microstructure (4) ──────────────────────────────────────────────


def test_tsi_constant_input_yields_zero_or_none() -> None:
    """All identical closes → no price changes → TSI undefined or 0."""
    out = true_strength_index(closes=[100.0] * 50, long=25, short=13)
    defined = [v for v in out if v is not None]
    # When defined, the TSI should be 0 (numerator = 0).
    assert all(v == 0.0 for v in defined)


def test_tsi_returns_same_length() -> None:
    n = 100
    out = true_strength_index(
        closes=[100.0 + (i % 7) - 3.0 for i in range(n)], long=25, short=13
    )
    assert len(out) == n


def test_tsi_rejects_zero_long() -> None:
    with pytest.raises(ValueError, match="positive"):
        true_strength_index(closes=[1.0] * 50, long=0, short=13)


def test_ppo_rejects_fast_geq_slow() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        percent_price_oscillator(closes=[1.0] * 50, fast=26, slow=26, signal=9)


def test_ppo_constant_input_yields_zero() -> None:
    """Constant closes → fast == slow EMA → PPO numerator is 0."""
    out = percent_price_oscillator(closes=[100.0] * 50, fast=12, slow=26, signal=9)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


def test_roc_volume_known_window() -> None:
    """volumes = 100 then 110: ROC(period=1) = 10%."""
    out = rate_of_change_volume(volumes=[100.0, 110.0, 121.0], period=1)
    assert out[1] == pytest.approx(10.0)
    assert out[2] == pytest.approx(10.0)


def test_roc_volume_zero_prev_returns_none() -> None:
    """Prior volume zero → div-by-zero would happen; we return None."""
    out = rate_of_change_volume(volumes=[0.0, 100.0, 110.0], period=1)
    assert out[1] is None  # prev = 0


def test_nvi_seeds_at_thousand() -> None:
    out = negative_volume_index(closes=[100.0] * 5, volumes=[1.0] * 5)
    assert out[0] == 1000.0


def test_nvi_only_updates_on_volume_down_days() -> None:
    closes = [100.0, 110.0, 120.0]
    volumes = [10.0, 5.0, 20.0]  # bar 1 vol down; bar 2 vol up
    out = negative_volume_index(closes=closes, volumes=volumes)
    assert out[0] == 1000.0
    assert out[1] == pytest.approx(1100.0)  # 1000 + 1000 * 0.10
    assert out[2] == out[1]  # bar 2 vol-up → unchanged


# ─── Order Flow Proxy (4) ────────────────────────────────────────────


def test_money_flow_ratio_balanced_window_yields_one() -> None:
    """Symmetric up+down moves of equal magnitude → ratio ≈ 1."""
    n = 30
    # Alternate up/down with same volume + magnitude.
    highs = []
    lows = []
    closes = []
    for i in range(n):
        if i % 2 == 0:
            closes.append(100.0)
        else:
            closes.append(100.5)
        highs.append(closes[i] + 0.5)
        lows.append(closes[i] - 0.5)
    out = money_flow_ratio(
        highs=highs, lows=lows, closes=closes, volumes=[10.0] * n, period=14
    )
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(1.0, abs=0.5)


def test_money_flow_ratio_no_down_money_returns_inf() -> None:
    """Strictly up window → no down-money → ratio is +inf."""
    n = 30
    closes = [100.0 + i for i in range(n)]  # strict uptrend
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    out = money_flow_ratio(
        highs=highs, lows=lows, closes=closes, volumes=[10.0] * n, period=14
    )
    last = out[-1]
    assert last is not None
    assert math.isinf(last)


def test_obv_ema_returns_same_length() -> None:
    n = 30
    out = on_balance_volume_ema(
        closes=[100.0 + (i % 5) for i in range(n)],
        volumes=[10.0] * n,
        ema_period=21,
    )
    assert len(out) == n


def test_cumulative_volume_delta_bull_only_accumulates_positive() -> None:
    """Always-bullish bars → CVD is monotone non-decreasing."""
    n = 10
    out = cumulative_volume_delta(
        opens=[100.0] * n, closes=[101.0] * n, volumes=[10.0] * n
    )
    assert out[-1] == pytest.approx(100.0)  # 10 bars * +10
    for i in range(1, len(out)):
        assert (out[i] or 0.0) >= (out[i - 1] or 0.0)


def test_cumulative_volume_delta_bear_only_accumulates_negative() -> None:
    n = 10
    out = cumulative_volume_delta(
        opens=[100.0] * n, closes=[99.0] * n, volumes=[10.0] * n
    )
    assert out[-1] == pytest.approx(-100.0)


def test_buying_pressure_ratio_all_bull_returns_one() -> None:
    out = buying_pressure_ratio(
        opens=[100.0] * 30, closes=[101.0] * 30, volumes=[10.0] * 30, period=20
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(1.0) for v in defined)


def test_buying_pressure_ratio_all_bear_returns_zero() -> None:
    out = buying_pressure_ratio(
        opens=[100.0] * 30, closes=[99.0] * 30, volumes=[10.0] * 30, period=20
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(0.0) for v in defined)


# ─── Registry promotion ──────────────────────────────────────────────


_PACK10_IDS = {
    "volume_weighted_avg_close",
    "volume_at_price_high",
    "volume_breakout",
    "positive_volume_index",
    "true_strength_index",
    "percent_price_oscillator",
    "rate_of_change_volume",
    "negative_volume_index",
    "money_flow_ratio",
    "on_balance_volume_ema",
    "cumulative_volume_delta",
    "buying_pressure_ratio",
}


def test_pack10_module_exposes_twelve_indicators() -> None:
    assert len(PACK10_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK10_ACTIVE_INDICATORS} == _PACK10_IDS


def test_pack10_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK10_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack10_is_one_hundred_thirty_one() -> None:
    """Pack-9 baseline 119 + 12 Pack 10 = 131."""
    assert len(get_active_indicators()) >= 131


def test_pack10_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK10_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack10_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK10_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


# ─── Backtest dispatch ──────────────────────────────────────────────


def _wavy_candles(n: int = 80) -> list:
    out = []
    for i in range(n):
        base = 100.0 + (i % 9) - 4.0
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
        ("volume_weighted_avg_close", {"period": 14}),
        ("volume_at_price_high", {"period": 60, "bins": 50}),
        ("volume_breakout", {"period": 20, "spike_mult": 2.0}),
        ("positive_volume_index", {}),
        ("true_strength_index", {"long": 25, "short": 13}),
        ("percent_price_oscillator", {"fast": 12, "slow": 26, "signal": 9}),
        ("rate_of_change_volume", {"period": 14}),
        ("negative_volume_index", {}),
        ("money_flow_ratio", {"period": 14}),
        ("on_balance_volume_ema", {"ema_period": 21}),
        ("cumulative_volume_delta", {}),
        ("buying_pressure_ratio", {"period": 20}),
    ],
)
def test_pack10_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 10 indicator dispatches successfully and produces
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


# ─── Pine importer ──────────────────────────────────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Pack 10 importer test")
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


def test_pine_tsi_maps_to_true_strength_index() -> None:
    """ta.tsi(source, short, long) → preserved arg order: short
    BEFORE long in Pine, but our calc takes long BEFORE short."""
    src = _wrap("tsi_val = ta.tsi(close, 13, 25)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "tsi_val" in inds
    assert inds["tsi_val"]["type"] == "true_strength_index"
    assert inds["tsi_val"]["params"] == {"long": 25, "short": 13}


def test_pine_ppo_maps_to_percent_price_oscillator() -> None:
    src = _wrap("ppo_val = ta.ppo(12, 26, 9)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "ppo_val" in inds
    assert inds["ppo_val"]["type"] == "percent_price_oscillator"
    assert inds["ppo_val"]["params"] == {"fast": 12, "slow": 26, "signal": 9}
