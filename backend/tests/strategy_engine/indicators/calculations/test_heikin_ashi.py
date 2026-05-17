"""Heikin-Ashi tests — math validation + edge cases + reference compare.

Reference: TradingView's Pine Script and pandas-ta both implement the
canonical formulas:
    ha_close = (o + h + l + c) / 4
    ha_open  = (prev_ha_open + prev_ha_close) / 2      (seed: (o[0]+c[0])/2)
    ha_high  = max(h, ha_open, ha_close)
    ha_low   = min(l, ha_open, ha_close)
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators.calculations.heikin_ashi import heikin_ashi


# ─── Edge cases ────────────────────────────────────────────────────────


def test_empty_input_returns_empty() -> None:
    assert heikin_ashi([], [], [], []) == []


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        heikin_ashi([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0])


# ─── Seed semantics ─────────────────────────────────────────────────────


def test_single_bar_seed_uses_open_close_average() -> None:
    """Seed: ha_open[0] = (o[0] + c[0]) / 2; ha_close[0] = (o+h+l+c)/4."""
    result = heikin_ashi([10.0], [12.0], [8.0], [11.0])
    assert len(result) == 1
    bar = result[0]
    assert bar is not None
    assert bar["close"] == pytest.approx((10 + 12 + 8 + 11) / 4)
    assert bar["open"] == pytest.approx((10 + 11) / 2)
    # high/low include ha_open + ha_close in the max/min
    assert bar["high"] == pytest.approx(max(12.0, bar["open"], bar["close"]))
    assert bar["low"] == pytest.approx(min(8.0, bar["open"], bar["close"]))


# ─── Recursive formula ─────────────────────────────────────────────────


def test_second_bar_recursive_open() -> None:
    """ha_open[1] = (ha_open[0] + ha_close[0]) / 2."""
    o = [10.0, 11.0]
    h = [12.0, 13.0]
    l = [9.0, 10.0]
    c = [11.0, 12.0]
    result = heikin_ashi(o, h, l, c)
    bar0 = result[0]
    bar1 = result[1]
    assert bar0 is not None and bar1 is not None
    expected_ha_open_1 = (bar0["open"] + bar0["close"]) / 2
    assert bar1["open"] == pytest.approx(expected_ha_open_1)


def test_third_bar_continues_recursion() -> None:
    o = [10.0, 11.0, 12.0]
    h = [12.0, 13.0, 14.0]
    l = [9.0, 10.0, 11.0]
    c = [11.0, 12.0, 13.0]
    result = heikin_ashi(o, h, l, c)
    bar1, bar2 = result[1], result[2]
    assert bar1 is not None and bar2 is not None
    expected = (bar1["open"] + bar1["close"]) / 2
    assert bar2["open"] == pytest.approx(expected)


# ─── HA high/low invariant ─────────────────────────────────────────────


def test_ha_high_geq_open_close_and_input_high() -> None:
    o = [100.0, 102.0, 99.0]
    h = [103.0, 105.0, 101.0]
    l = [98.0, 100.0, 96.0]
    c = [102.0, 103.0, 97.0]
    result = heikin_ashi(o, h, l, c)
    for i, bar in enumerate(result):
        assert bar is not None
        assert bar["high"] >= bar["open"]
        assert bar["high"] >= bar["close"]
        assert bar["high"] >= h[i]


def test_ha_low_leq_open_close_and_input_low() -> None:
    o = [100.0, 102.0, 99.0]
    h = [103.0, 105.0, 101.0]
    l = [98.0, 100.0, 96.0]
    c = [102.0, 103.0, 97.0]
    result = heikin_ashi(o, h, l, c)
    for i, bar in enumerate(result):
        assert bar is not None
        assert bar["low"] <= bar["open"]
        assert bar["low"] <= bar["close"]
        assert bar["low"] <= l[i]


# ─── Output length matches input ───────────────────────────────────────


def test_output_length_matches_input() -> None:
    o = [float(i) for i in range(50)]
    h = [float(i) + 1.0 for i in range(50)]
    l = [float(i) - 1.0 for i in range(50)]
    c = [float(i) + 0.5 for i in range(50)]
    result = heikin_ashi(o, h, l, c)
    assert len(result) == 50
    assert all(bar is not None for bar in result)


# ─── Flat-line input → flat HA ─────────────────────────────────────────


def test_flat_line_input_produces_flat_ha() -> None:
    """Constant OHLC = K means ha_close = K and ha_open converges to K."""
    o = h = l = c = [100.0] * 20
    result = heikin_ashi(o, h, l, c)
    for bar in result:
        assert bar is not None
        assert bar["close"] == pytest.approx(100.0)
        assert bar["open"] == pytest.approx(100.0)
        assert bar["high"] == pytest.approx(100.0)
        assert bar["low"] == pytest.approx(100.0)


# ─── Reference golden values (hand-computed) ───────────────────────────


def test_reference_three_bar_uptrend() -> None:
    """Hand-computed values for a 3-bar uptrend.

    o = [100, 105, 110]
    h = [102, 107, 112]
    l = [99,  104, 109]
    c = [101, 106, 111]

    Bar 0:
      ha_close[0] = (100+102+99+101)/4 = 100.5
      ha_open[0]  = (100+101)/2        = 100.5
      ha_high[0]  = max(102, 100.5, 100.5) = 102
      ha_low[0]   = min(99, 100.5, 100.5)  = 99

    Bar 1:
      ha_close[1] = (105+107+104+106)/4 = 105.5
      ha_open[1]  = (100.5 + 100.5)/2   = 100.5
      ha_high[1]  = max(107, 100.5, 105.5) = 107
      ha_low[1]   = min(104, 100.5, 105.5) = 100.5

    Bar 2:
      ha_close[2] = (110+112+109+111)/4 = 110.5
      ha_open[2]  = (100.5 + 105.5)/2   = 103.0
      ha_high[2]  = max(112, 103.0, 110.5) = 112
      ha_low[2]   = min(109, 103.0, 110.5) = 103.0
    """
    result = heikin_ashi(
        [100.0, 105.0, 110.0],
        [102.0, 107.0, 112.0],
        [99.0, 104.0, 109.0],
        [101.0, 106.0, 111.0],
    )
    assert len(result) == 3
    assert result[0] == {"open": 100.5, "high": 102.0, "low": 99.0, "close": 100.5}
    assert result[1] == {"open": 100.5, "high": 107.0, "low": 100.5, "close": 105.5}
    assert result[2] == {"open": 103.0, "high": 112.0, "low": 103.0, "close": 110.5}


def test_long_input_no_nans_after_seed() -> None:
    """No NaN should appear in HA output for valid finite input."""
    import random

    rng = random.Random(42)
    n = 200
    o = [100.0 + rng.gauss(0, 1) for _ in range(n)]
    h = [v + abs(rng.gauss(0, 1)) for v in o]
    l = [v - abs(rng.gauss(0, 1)) for v in o]
    c = [(hi + lo) / 2 + rng.gauss(0, 0.1) for hi, lo in zip(h, l, strict=True)]
    # Ensure OHLC validity (l <= o,c <= h)
    for i in range(n):
        c[i] = max(l[i], min(h[i], c[i]))
    result = heikin_ashi(o, h, l, c)
    assert len(result) == n
    for bar in result:
        assert bar is not None
        for v in bar.values():
            assert not math.isnan(v)
            assert not math.isinf(v)


def test_uniform_uptrend_ha_close_increases_monotonically() -> None:
    o = [100.0 + i for i in range(20)]
    h = [101.0 + i for i in range(20)]
    l = [99.0 + i for i in range(20)]
    c = [100.5 + i for i in range(20)]
    result = heikin_ashi(o, h, l, c)
    closes = [bar["close"] for bar in result if bar is not None]
    for a, b in zip(closes, closes[1:], strict=False):
        assert b > a
