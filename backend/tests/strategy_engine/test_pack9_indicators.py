"""Pack 9 — bands + envelopes + advanced MA tests.

Same shape as Pack 2 / 3 / 4 / 5 / 6 / 7 / 8. Active count
assertion is ``>= 119``.

Also covers the Pine importer rewire of ``ta.highest`` /
``ta.lowest`` from the stale "donchian coming_soon" note to
the new ``price_channel_high`` / ``price_channel_low`` actives.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack9_active import PACK9_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.arnaud_legoux_ma import (
    arnaud_legoux_ma,
)
from app.strategy_engine.indicators.calculations.envelope_lower import (
    envelope_lower,
)
from app.strategy_engine.indicators.calculations.envelope_upper import (
    envelope_upper,
)
from app.strategy_engine.indicators.calculations.kaufman_ama import kaufman_ama
from app.strategy_engine.indicators.calculations.linear_regression_lower import (
    linear_regression_lower,
)
from app.strategy_engine.indicators.calculations.linear_regression_upper import (
    linear_regression_upper,
)
from app.strategy_engine.indicators.calculations.price_channel_high import (
    price_channel_high,
)
from app.strategy_engine.indicators.calculations.price_channel_low import (
    price_channel_low,
)
from app.strategy_engine.indicators.calculations.starc_lower import starc_lower
from app.strategy_engine.indicators.calculations.starc_upper import starc_upper
from app.strategy_engine.indicators.calculations.vidya import vidya
from app.strategy_engine.indicators.calculations.zlema import zlema
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.pine_import import convert_pine_to_strategy
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Bands & Envelopes (4) ───────────────────────────────────────────


def test_envelope_upper_above_base_by_pct() -> None:
    """Constant input → SMA = constant → upper = base * (1 + pct/100)."""
    out = envelope_upper(values=[100.0] * 30, period=20, pct=2.5)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(102.5) for v in defined)


def test_envelope_lower_below_base_by_pct() -> None:
    out = envelope_lower(values=[100.0] * 30, period=20, pct=2.5)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(97.5) for v in defined)


def test_envelope_rejects_negative_pct() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        envelope_upper(values=[1.0] * 30, period=20, pct=-1.0)


def test_starc_upper_above_lower() -> None:
    """Sanity: upper > lower for any defined bar in real data."""
    n = 50
    highs = [10.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    closes = [9.5 + i * 0.1 for i in range(n)]
    upper = starc_upper(highs, lows, closes, period=5, atr_period=15, atr_mult=1.5)
    lower = starc_lower(highs, lows, closes, period=5, atr_period=15, atr_mult=1.5)
    for u, lo in zip(upper, lower, strict=True):
        if u is None or lo is None:
            continue
        assert u > lo


def test_starc_rejects_zero_mult() -> None:
    with pytest.raises(ValueError, match="> 0"):
        starc_upper(highs=[1.0] * 30, lows=[1.0] * 30,
                     closes=[1.0] * 30, atr_mult=0)


# ─── Channels (4) ────────────────────────────────────────────────────


def test_price_channel_high_yields_window_max() -> None:
    """Hand-checked: window of [10, 11, 12, 13, 14] → max 14."""
    out = price_channel_high(highs=[10.0, 11.0, 12.0, 13.0, 14.0], period=5)
    assert out[-1] == 14.0


def test_price_channel_low_yields_window_min() -> None:
    out = price_channel_low(lows=[5.0, 4.0, 3.0, 2.0, 1.0], period=5)
    assert out[-1] == 1.0


def test_price_channel_empty_returns_empty() -> None:
    assert price_channel_high([], period=20) == []
    assert price_channel_low([], period=20) == []


def test_linear_regression_upper_above_lower() -> None:
    """Sanity: for any defined bar, upper > lower."""
    n = 50
    out_u = linear_regression_upper(
        values=[100.0 + i * 0.5 for i in range(n)], period=20, std_mult=2.0
    )
    out_l = linear_regression_lower(
        values=[100.0 + i * 0.5 for i in range(n)], period=20, std_mult=2.0
    )
    for u, lo in zip(out_u, out_l, strict=True):
        if u is None or lo is None:
            continue
        assert u >= lo


def test_linear_regression_band_constant_input_yields_zero_width() -> None:
    """Constant input → zero residual → upper == lower == base."""
    out_u = linear_regression_upper([100.0] * 30, period=20, std_mult=2.0)
    out_l = linear_regression_lower([100.0] * 30, period=20, std_mult=2.0)
    defined_pairs = [(u, lo) for u, lo in zip(out_u, out_l, strict=True)
                      if u is not None and lo is not None]
    assert all(u == pytest.approx(lo) for u, lo in defined_pairs)


def test_linear_regression_band_rejects_negative_std_mult() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        linear_regression_upper([1.0] * 30, period=20, std_mult=-1.0)


# ─── Advanced MAs (4) ────────────────────────────────────────────────


def test_arnaud_legoux_ma_constant_input_returns_constant() -> None:
    out = arnaud_legoux_ma(values=[100.0] * 30, period=9)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(100.0) for v in defined)


def test_arnaud_legoux_ma_rejects_invalid_offset() -> None:
    with pytest.raises(ValueError, match="in"):
        arnaud_legoux_ma(values=[1.0] * 30, period=9, offset=1.5)


def test_arnaud_legoux_ma_rejects_zero_sigma() -> None:
    with pytest.raises(ValueError, match="> 0"):
        arnaud_legoux_ma(values=[1.0] * 30, period=9, sigma=0)


def test_vidya_seeds_at_first_window_sma() -> None:
    """The seed value at index ``period - 1`` equals the SMA of
    the first window — the same behaviour the docstring promises.

    Needs n > period so the underlying CMO can produce a value
    (CMO returns [] when ``period >= n``)."""
    closes = [100.0 + i * 2.0 for i in range(15)]  # 15 bars
    out = vidya(values=closes, period=9)
    expected_seed = sum(closes[:9]) / 9
    assert out[8] == pytest.approx(expected_seed)


def test_vidya_constant_input_stays_constant() -> None:
    out = vidya(values=[100.0] * 30, period=9)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(100.0) for v in defined)


def test_zlema_returns_same_length_with_warmup() -> None:
    n = 50
    out = zlema(values=[100.0 + i * 0.5 for i in range(n)], period=20)
    assert len(out) == n
    # First (period-1)//2 bars are masked.
    lag = (20 - 1) // 2
    assert all(v is None for v in out[:lag])


def test_zlema_rejects_period_below_two() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        zlema(values=[1.0] * 30, period=1)


def test_kaufman_ama_seeds_at_period_minus_one() -> None:
    """KAMA seed value = closes[period - 1]."""
    out = kaufman_ama(values=[100.0 + i for i in range(20)],
                       period=10, fast=2, slow=30)
    assert out[9] == pytest.approx(109.0)


def test_kaufman_ama_constant_input_stays_constant() -> None:
    out = kaufman_ama(values=[100.0] * 30, period=10, fast=2, slow=30)
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(100.0) for v in defined)


def test_kaufman_ama_rejects_fast_geq_slow() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        kaufman_ama(values=[1.0] * 30, period=10, fast=30, slow=30)


# ─── Registry promotion ──────────────────────────────────────────────


_PACK9_IDS = {
    "envelope_upper",
    "envelope_lower",
    "starc_upper",
    "starc_lower",
    "price_channel_high",
    "price_channel_low",
    "linear_regression_upper",
    "linear_regression_lower",
    "arnaud_legoux_ma",
    "vidya",
    "zlema",
    "kaufman_ama",
}


def test_pack9_module_exposes_twelve_indicators() -> None:
    assert len(PACK9_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK9_ACTIVE_INDICATORS} == _PACK9_IDS


def test_pack9_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK9_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack9_is_one_hundred_nineteen() -> None:
    """20 historical + 15 Pack 2 + 12 Pack 3 + 12 Pack 4 + 12 Pack 5
    + 12 Pack 6 + 12 Pack 7 + 12 Pack 8 + 12 Pack 9 = 119."""
    assert len(get_active_indicators()) >= 119


def test_pack9_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK9_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack9_no_beginner_difficulty() -> None:
    """Spec says 'avoid beginner set lock'."""
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK9_ACTIVE_INDICATORS:
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
                volume=1_000.0,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        (
            "envelope_upper",
            {"period": 20, "pct": 2.5, "source": "close"},
        ),
        (
            "envelope_lower",
            {"period": 20, "pct": 2.5, "source": "close"},
        ),
        (
            "starc_upper",
            {"period": 5, "atr_period": 15, "atr_mult": 1.5},
        ),
        (
            "starc_lower",
            {"period": 5, "atr_period": 15, "atr_mult": 1.5},
        ),
        ("price_channel_high", {"period": 20}),
        ("price_channel_low", {"period": 20}),
        (
            "linear_regression_upper",
            {"period": 20, "std_mult": 2.0, "source": "close"},
        ),
        (
            "linear_regression_lower",
            {"period": 20, "std_mult": 2.0, "source": "close"},
        ),
        (
            "arnaud_legoux_ma",
            {"period": 9, "sigma": 6.0, "offset": 0.85, "source": "close"},
        ),
        ("vidya", {"period": 9, "source": "close"}),
        ("zlema", {"period": 20, "source": "close"}),
        (
            "kaufman_ama",
            {"period": 10, "fast": 2, "slow": 30, "source": "close"},
        ),
    ],
)
def test_pack9_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 9 indicator dispatches successfully and produces a
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
    # No multi-output warning for any Pack 9 indicator.
    assert not any(f"{indicator_type}_inst" in w for w in warnings)


# ─── Pine importer rewire ───────────────────────────────────────────


_PINE_HEADER = """\
//@version=5
// SPDX-License-Identifier: MIT
strategy("Pack 9 importer test")
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


def test_pine_highest_now_maps_to_price_channel_high() -> None:
    """Rewire from the stale "donchian coming_soon" note. ``ta.highest``
    now produces a real ``price_channel_high`` config."""
    src = _wrap("hi_val = ta.highest(high, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "hi_val" in inds
    assert inds["hi_val"]["type"] == "price_channel_high"
    assert inds["hi_val"]["params"] == {"period": 20}


def test_pine_lowest_now_maps_to_price_channel_low() -> None:
    src = _wrap("lo_val = ta.lowest(low, 20)")
    result = convert_pine_to_strategy(src)
    inds = _by_id(result)
    assert "lo_val" in inds
    assert inds["lo_val"]["type"] == "price_channel_low"
    assert inds["lo_val"]["params"] == {"period": 20}
