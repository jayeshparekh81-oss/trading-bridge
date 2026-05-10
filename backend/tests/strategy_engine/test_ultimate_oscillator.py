"""Ultimate Oscillator calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.ultimate_oscillator import (
    ultimate_oscillator,
)


def _series(n: int, slope: float = 1.0) -> tuple[list[float], list[float], list[float]]:
    closes = [100.0 + slope * i for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    return highs, lows, closes


def test_uo_output_length_parity_and_seed_index() -> None:
    highs, lows, closes = _series(40)
    out = ultimate_oscillator(highs, lows, closes, 7, 14, 28)
    assert len(out) == 40
    # Long period is 28; first defined value at index 28.
    assert out[27] is None
    assert out[28] is not None


def test_uo_uptrend_with_close_at_high_pegs_at_100() -> None:
    """Each bar opens at prev_close and closes at the high → BP == TR → UO = 100.

    This is the only synthetic shape that peg-tests UO at 100: the
    reference low (``min(low, prev_close)``) must equal ``prev_close``
    AND the close must equal the reference high.
    """
    n = 50
    closes = [100.0 + i for i in range(n)]  # rises by 1 per bar
    # low == prev_close means BP / TR ratio is exactly 1.
    lows = [closes[0]] + [closes[i - 1] for i in range(1, n)]
    highs = closes  # close at the high
    out = ultimate_oscillator(highs, lows, closes, 7, 14, 28)
    last = out[-1]
    assert last is not None
    assert abs(last - 100.0) < 1e-9


def test_uo_downtrend_with_close_at_low_pegs_at_0() -> None:
    """Symmetric peg-test for the floor: close at low, prev_close at high."""
    n = 50
    closes = [100.0 - i for i in range(n)]
    highs = [closes[0]] + [closes[i - 1] for i in range(1, n)]  # high == prev_close
    lows = closes  # close at the low
    out = ultimate_oscillator(highs, lows, closes, 7, 14, 28)
    last = out[-1]
    assert last is not None
    assert abs(last - 0.0) < 1e-9


def test_uo_range_is_zero_to_one_hundred() -> None:
    highs, lows, closes = _series(60, slope=0.5)
    out = ultimate_oscillator(highs, lows, closes, 7, 14, 28)
    for v in out:
        if v is not None:
            assert 0.0 <= v <= 100.0


def test_uo_short_input_returns_empty() -> None:
    highs, lows, closes = _series(15)
    assert ultimate_oscillator(highs, lows, closes, 7, 14, 28) == []


def test_uo_rejects_unordered_periods() -> None:
    highs, lows, closes = _series(40)
    with pytest.raises(ValueError):
        ultimate_oscillator(highs, lows, closes, 14, 7, 28)


def test_uo_rejects_non_positive_period() -> None:
    highs, lows, closes = _series(40)
    with pytest.raises(ValueError):
        ultimate_oscillator(highs, lows, closes, 0, 14, 28)


def test_uo_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        ultimate_oscillator([1.0, 2.0], [1.0], [1.0, 2.0])
