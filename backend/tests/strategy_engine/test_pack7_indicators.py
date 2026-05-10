"""Pack 7 — trend strength + advanced momentum tests.

Same shape as Pack 2 / 3 / 4 / 5 / 6 — every pack pins its own
delta in its own file. Active count assertion is ``>= 95`` (loose
lower bound for forward compat).
"""

from __future__ import annotations

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack7_active import PACK7_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.aroon_down import aroon_down
from app.strategy_engine.indicators.calculations.aroon_oscillator import (
    aroon_oscillator,
)
from app.strategy_engine.indicators.calculations.aroon_up import aroon_up
from app.strategy_engine.indicators.calculations.balance_of_power import (
    balance_of_power,
)
from app.strategy_engine.indicators.calculations.chande_kroll_stop import (
    chande_kroll_stop,
)
from app.strategy_engine.indicators.calculations.coppock_curve import (
    coppock_curve,
)
from app.strategy_engine.indicators.calculations.detrended_price_oscillator import (
    detrended_price_oscillator,
)
from app.strategy_engine.indicators.calculations.fisher_transform import (
    fisher_transform,
)
from app.strategy_engine.indicators.calculations.klinger_volume_oscillator import (
    klinger_volume_oscillator,
)
from app.strategy_engine.indicators.calculations.relative_vigor_index import (
    relative_vigor_index,
)
from app.strategy_engine.indicators.calculations.vortex_negative import (
    vortex_negative,
)
from app.strategy_engine.indicators.calculations.vortex_positive import (
    vortex_positive,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.pine_import import convert_pine_to_strategy
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Trend Strength (5) ──────────────────────────────────────────────


def test_aroon_up_monotone_uptrend_yields_one_hundred() -> None:
    """Monotone-rising highs → newest bar is always the high → up = 100."""
    n = 30
    out = aroon_up(highs=[i * 1.0 for i in range(n)], lows=[i * 0.5 for i in range(n)],
                    period=14)
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(v == 100.0 for v in defined)


def test_aroon_down_monotone_uptrend_yields_zero() -> None:
    """Monotone-rising lows → newest bar is never the low → down → 0."""
    n = 30
    out = aroon_down(highs=[i * 1.0 for i in range(n)], lows=[i * 0.5 for i in range(n)],
                      period=14)
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    # Last bar's lowest-low is the OLDEST in the window → down → 0.
    assert out[-1] == 0.0


def test_aroon_oscillator_is_up_minus_down() -> None:
    """Sanity: oscillator equals up - down for every defined bar."""
    n = 30
    highs = [10.0 + (i % 5) for i in range(n)]
    lows = [8.0 + (i % 5) for i in range(n)]
    up = aroon_up(highs, lows, period=14)
    down = aroon_down(highs, lows, period=14)
    osc = aroon_oscillator(highs, lows, period=14)
    for i, value in enumerate(osc):
        if value is None:
            continue
        assert up[i] is not None
        assert down[i] is not None
        # type: ignore[operator] — guarded by the None checks.
        assert value == pytest.approx(up[i] - down[i])  # type: ignore[operator]


def test_vortex_positive_returns_same_length() -> None:
    n = 30
    out = vortex_positive(
        highs=[10.0 + i * 0.1 for i in range(n)],
        lows=[9.0 + i * 0.1 for i in range(n)],
        closes=[9.5 + i * 0.1 for i in range(n)],
        period=14,
    )
    assert len(out) == n
    assert all(v is None for v in out[:14])
    assert all(v is not None for v in out[14:])


def test_vortex_negative_uptrend_stays_below_positive() -> None:
    """In a clean uptrend VI+ should dominate VI-."""
    n = 50
    highs = [10.0 + i * 0.5 for i in range(n)]
    lows = [9.0 + i * 0.5 for i in range(n)]
    closes = [9.5 + i * 0.5 for i in range(n)]
    pos = vortex_positive(highs, lows, closes, period=14)
    neg = vortex_negative(highs, lows, closes, period=14)
    # Compare last bar — a clean uptrend should have VI+ > VI-.
    assert pos[-1] is not None
    assert neg[-1] is not None
    assert pos[-1] > neg[-1]  # type: ignore[operator]


def test_vortex_empty_returns_empty() -> None:
    assert vortex_positive([], [], [], period=14) == []
    assert vortex_negative([], [], [], period=14) == []


# ─── Advanced Momentum (4) ───────────────────────────────────────────


def test_klinger_rejects_fast_geq_slow() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        klinger_volume_oscillator(
            highs=[1.0] * 100,
            lows=[1.0] * 100,
            closes=[1.0] * 100,
            volumes=[1.0] * 100,
            fast=55,
            slow=55,
        )


def test_klinger_returns_same_length() -> None:
    n = 100
    out = klinger_volume_oscillator(
        highs=[10.0 + (i % 7) for i in range(n)],
        lows=[8.0 + (i % 7) for i in range(n)],
        closes=[9.0 + (i % 7) for i in range(n)],
        volumes=[1000.0] * n,
        fast=34,
        slow=55,
    )
    assert len(out) == n


def test_dpo_rejects_period_below_two() -> None:
    with pytest.raises(ValueError, match="> 1"):
        detrended_price_oscillator([1.0] * 30, period=1)


def test_dpo_returns_same_length_with_warmup() -> None:
    n = 50
    out = detrended_price_oscillator([100.0 + i * 0.1 for i in range(n)], period=20)
    assert len(out) == n
    # First period-1 bars are None.
    assert all(v is None for v in out[:19])
    # Some defined values exist.
    assert any(v is not None for v in out)


def test_coppock_insufficient_returns_empty() -> None:
    """Needs max(short, long) + wma_period bars."""
    out = coppock_curve(closes=[100.0] * 10, short_period=11, long_period=14, wma_period=10)
    assert out == []


def test_coppock_returns_same_length_with_warmup() -> None:
    n = 60
    out = coppock_curve(closes=[100.0 + i * 0.5 for i in range(n)],
                         short_period=11, long_period=14, wma_period=10)
    assert len(out) == n
    # Warm-up ensures the first ``max(short, long) + wma - 1`` indices are None.
    assert out[0] is None
    assert any(v is not None for v in out)


def test_fisher_rejects_period_below_two() -> None:
    with pytest.raises(ValueError, match="> 1"):
        fisher_transform(highs=[1.0] * 30, lows=[1.0] * 30, period=1)


def test_fisher_constant_input_yields_zero() -> None:
    """Constant input → flat range → raw stays 0 → fish stays 0."""
    out = fisher_transform(highs=[10.0] * 30, lows=[10.0] * 30, period=9)
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


# ─── Oscillators (3) ─────────────────────────────────────────────────


def test_chande_kroll_stop_returns_same_length() -> None:
    n = 50
    out = chande_kroll_stop(
        highs=[10.0 + i * 0.1 for i in range(n)],
        lows=[9.0 + i * 0.1 for i in range(n)],
        closes=[9.5 + i * 0.1 for i in range(n)],
        atr_period=10, atr_mult=1.0, period=9,
    )
    assert len(out) == n
    # Warm-up bars are None (atr_period + period - 2 = 17).
    assert all(v is None for v in out[:17])


def test_chande_kroll_rejects_zero_mult() -> None:
    with pytest.raises(ValueError, match="> 0"):
        chande_kroll_stop(highs=[1.0] * 30, lows=[1.0] * 30,
                          closes=[1.0] * 30, atr_mult=0)


def test_relative_vigor_index_returns_same_length() -> None:
    n = 40
    out = relative_vigor_index(
        opens=[10.0] * n,
        highs=[10.5] * n,
        lows=[9.5] * n,
        closes=[10.2] * n,
        period=14,
    )
    assert len(out) == n


def test_relative_vigor_index_insufficient_returns_empty() -> None:
    """Needs period + 3 bars (smoothing eats 3)."""
    out = relative_vigor_index(opens=[1.0] * 5, highs=[1.0] * 5,
                                 lows=[1.0] * 5, closes=[1.0] * 5, period=14)
    assert out == []


def test_balance_of_power_close_at_open_yields_zero() -> None:
    """Close == open → numerator zero → BoP = 0."""
    out = balance_of_power(opens=[10.0] * 5, highs=[11.0] * 5,
                            lows=[9.0] * 5, closes=[10.0] * 5)
    assert all(v == 0.0 for v in out)


def test_balance_of_power_close_at_high_yields_one() -> None:
    """Close == high, open == low → BoP = +1."""
    out = balance_of_power(opens=[9.0] * 3, highs=[11.0] * 3,
                            lows=[9.0] * 3, closes=[11.0] * 3)
    assert all(v == 1.0 for v in out)


def test_balance_of_power_flat_bar_yields_zero() -> None:
    out = balance_of_power(opens=[10.0], highs=[10.0], lows=[10.0], closes=[10.0])
    assert out == [0.0]


# ─── Registry promotion ──────────────────────────────────────────────


_PACK7_IDS = {
    "aroon_up",
    "aroon_down",
    "aroon_oscillator",
    "vortex_positive",
    "vortex_negative",
    "klinger_volume_oscillator",
    "detrended_price_oscillator",
    "coppock_curve",
    "fisher_transform",
    "chande_kroll_stop",
    "relative_vigor_index",
    "balance_of_power",
}


def test_pack7_module_exposes_twelve_indicators() -> None:
    assert len(PACK7_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK7_ACTIVE_INDICATORS} == _PACK7_IDS


def test_pack7_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK7_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack7_is_ninety_five() -> None:
    """20 historical + 15 Pack 2 + 12 Pack 3 + 12 Pack 4 + 12 Pack 5
    + 12 Pack 6 + 12 Pack 7 = 95.

    Loose lower bound for forward compatibility — each pack pins
    its own delta in its own test file."""
    assert len(get_active_indicators()) >= 95


def test_pack7_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK7_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack7_no_beginner_difficulty() -> None:
    """Spec says 'avoid beginner set lock' — every Pack 7 entry
    must be INTERMEDIATE or EXPERT."""
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK7_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


# ─── Backtest dispatch ──────────────────────────────────────────────


def _wavy_candles(n: int = 100) -> list:
    """Synthetic OHLC with non-trivial range + volume."""
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
        ("aroon_up", {"period": 14}),
        ("aroon_down", {"period": 14}),
        ("aroon_oscillator", {"period": 14}),
        ("vortex_positive", {"period": 14}),
        ("vortex_negative", {"period": 14}),
        (
            "klinger_volume_oscillator",
            {"fast": 34, "slow": 55},
        ),
        ("detrended_price_oscillator", {"period": 20}),
        (
            "coppock_curve",
            {"short_period": 11, "long_period": 14, "wma_period": 10},
        ),
        ("fisher_transform", {"period": 9}),
        (
            "chande_kroll_stop",
            {"atr_period": 10, "atr_mult": 1.0, "period": 9},
        ),
        ("relative_vigor_index", {"period": 14}),
        ("balance_of_power", {}),
    ],
)
def test_pack7_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 7 indicator dispatches successfully and produces a
    same-length series."""
    candles = _wavy_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    # No multi-output warning for any Pack 7 indicator.
    assert not any(f"{indicator_type}_inst" in w for w in warnings)


# ─── Pine importer ──────────────────────────────────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Pack 7 importer test")
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


def test_pine_vortex_maps_to_vortex_positive_and_emits_note() -> None:
    """ta.vortex returns ``[VI+, VI-]``; we pick VI+ and surface a
    note pointing the user at the negative-line config they'd add
    separately."""
    src = _wrap("vi_val = ta.vortex(14)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "vi_val" in inds
    assert inds["vi_val"]["type"] == "vortex_positive"
    assert inds["vi_val"]["params"] == {"period": 14}
    notes = result.get("notes", [])
    assert any("VI-" in n for n in notes), notes  # type: ignore[union-attr]
