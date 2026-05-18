"""Fibonacci retracement tests.

Reference: standard retail-trading retracement formula.
Bullish: level = swing_low + (swing_high - swing_low) * pct
Bearish: level = swing_high - (swing_high - swing_low) * pct
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.fibonacci_retracement import (
    fibonacci_retracement,
)


def test_empty_input_returns_empty() -> None:
    assert fibonacci_retracement([], []) == []


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        fibonacci_retracement([1.0, 2.0], [1.0])


def test_invalid_lookback_raises() -> None:
    with pytest.raises(ValueError, match="lookback"):
        fibonacci_retracement([1.0] * 10, [0.5] * 10, lookback=1)


def test_invalid_direction_raises() -> None:
    with pytest.raises(ValueError, match="direction"):
        fibonacci_retracement([1.0] * 10, [0.5] * 10, direction="up")  # type: ignore[arg-type]


def test_warmup_emits_none() -> None:
    """First lookback-1 indices are None."""
    highs = [float(i) for i in range(50)]
    lows = [float(i) - 1.0 for i in range(50)]
    result = fibonacci_retracement(highs, lows, lookback=10)
    for v in result[:9]:
        assert v is None
    assert result[9] is not None


def test_output_length_matches_input() -> None:
    highs = [float(i) for i in range(50)]
    lows = [float(i) - 1.0 for i in range(50)]
    result = fibonacci_retracement(highs, lows, lookback=10)
    assert len(result) == 50


def test_bullish_retracement_levels() -> None:
    """In a window where high=100, low=50, range=50:
        23.6% level = 50 + 50*0.236 = 61.8
        38.2% level = 50 + 50*0.382 = 69.1
        50.0% level = 50 + 50*0.5   = 75.0
        61.8% level = 50 + 50*0.618 = 80.9
        78.6% level = 50 + 50*0.786 = 89.3
    """
    n = 10
    highs = [100.0] * n
    lows = [50.0] * n
    result = fibonacci_retracement(highs, lows, lookback=10, direction="bull")
    bar = result[-1]
    assert bar is not None
    assert bar["swing_high"] == 100.0
    assert bar["swing_low"] == 50.0
    assert bar["23.6"] == pytest.approx(61.8)
    assert bar["38.2"] == pytest.approx(69.1)
    assert bar["50.0"] == pytest.approx(75.0)
    assert bar["61.8"] == pytest.approx(80.9)
    assert bar["78.6"] == pytest.approx(89.3)


def test_bearish_retracement_levels() -> None:
    """In a window where high=100, low=50, range=50, bearish:
        level = high - range * pct
        23.6% = 100 - 50*0.236 = 88.2
        50%   = 75.0
        78.6% = 60.7
    """
    n = 10
    highs = [100.0] * n
    lows = [50.0] * n
    result = fibonacci_retracement(highs, lows, lookback=10, direction="bear")
    bar = result[-1]
    assert bar is not None
    assert bar["23.6"] == pytest.approx(88.2)
    assert bar["50.0"] == pytest.approx(75.0)
    assert bar["78.6"] == pytest.approx(60.7)


def test_50_percent_level_is_midpoint_regardless_of_direction() -> None:
    """50% retracement = midpoint between swing_high and swing_low,
    same for bull or bear."""
    highs = [100.0] * 10
    lows = [50.0] * 10
    bull = fibonacci_retracement(highs, lows, lookback=10, direction="bull")
    bear = fibonacci_retracement(highs, lows, lookback=10, direction="bear")
    assert bull[-1] is not None and bear[-1] is not None
    assert bull[-1]["50.0"] == pytest.approx(75.0)
    assert bear[-1]["50.0"] == pytest.approx(75.0)
    assert bull[-1]["50.0"] == bear[-1]["50.0"]


def test_flat_window_all_levels_collapse() -> None:
    """If high == low (flat window), all 5 fib levels equal swing_high."""
    highs = [100.0] * 10
    lows = [100.0] * 10
    result = fibonacci_retracement(highs, lows, lookback=10)
    bar = result[-1]
    assert bar is not None
    for key in ("23.6", "38.2", "50.0", "61.8", "78.6"):
        assert bar[key] == pytest.approx(100.0)


def test_rolling_window_picks_correct_swings() -> None:
    """In a 10-bar lookback, the swing high/low come from JUST THAT window."""
    # idx:        0      1      2      3      4      5      6      7      8      9      10     11     12
    highs = [50.0, 60.0, 100.0, 70.0, 60.0, 55.0, 50.0, 45.0, 40.0, 35.0, 80.0, 75.0, 70.0]
    lows = [40.0, 50.0, 90.0, 60.0, 50.0, 45.0, 40.0, 35.0, 30.0, 25.0, 70.0, 65.0, 60.0]
    result = fibonacci_retracement(highs, lows, lookback=10, direction="bull")
    # At idx 9 (window 0..9), swing high = 100 (idx 2), swing low = 25 (idx 9)
    bar9 = result[9]
    assert bar9 is not None
    assert bar9["swing_high"] == 100.0
    assert bar9["swing_low"] == 25.0
    # At idx 12 (window 3..12), swing high = 80 (idx 10), swing low = 25 (idx 9)
    bar12 = result[12]
    assert bar12 is not None
    assert bar12["swing_high"] == 80.0
    assert bar12["swing_low"] == 25.0


def test_known_input_golden_values() -> None:
    """Single golden hand-computed bar."""
    # window: 10 bars where high=22000, low=21500, range=500
    highs = [22000.0, 21800.0, 21900.0, 22000.0, 21900.0, 21850.0, 21750.0, 21700.0, 21600.0, 21500.0]
    lows = [21750.0, 21500.0, 21600.0, 21700.0, 21600.0, 21550.0, 21550.0, 21550.0, 21500.0, 21500.0]
    result = fibonacci_retracement(highs, lows, lookback=10, direction="bull")
    bar = result[-1]
    assert bar is not None
    assert bar["swing_high"] == 22000.0
    assert bar["swing_low"] == 21500.0
    rng = 500.0
    assert bar["23.6"] == pytest.approx(21500.0 + rng * 0.236)
    assert bar["38.2"] == pytest.approx(21500.0 + rng * 0.382)
    assert bar["50.0"] == pytest.approx(21500.0 + rng * 0.5)
    assert bar["61.8"] == pytest.approx(21500.0 + rng * 0.618)
    assert bar["78.6"] == pytest.approx(21500.0 + rng * 0.786)
