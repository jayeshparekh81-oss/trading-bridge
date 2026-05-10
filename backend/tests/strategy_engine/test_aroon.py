"""Aroon calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.aroon import aroon


def test_aroon_seeds_at_period_index() -> None:
    """Aroon is defined from index `period` (needs period + 1 bars)."""
    highs = [float(i) for i in range(20)]
    lows = [float(i) - 0.5 for i in range(20)]
    up, down, osc = aroon(highs, lows, period=10)
    assert up[9] is None
    assert up[10] is not None
    assert down[10] is not None
    assert osc[10] == up[10] - down[10]


def test_aroon_pure_uptrend_pegs_up_at_100() -> None:
    """When highs / lows both monotonically rise, the most recent bar is
    always the highest high — Aroon Up = 100, Aroon Down = 0 wherever
    the lowest low is also at the oldest window position."""
    highs = [float(i) for i in range(30)]
    lows = [float(i) - 1.0 for i in range(30)]
    up, down, osc = aroon(highs, lows, period=10)
    assert up[15] == 100.0
    assert down[15] == 0.0
    assert osc[15] == 100.0


def test_aroon_pure_downtrend_pegs_down_at_100() -> None:
    highs = [float(-i) for i in range(30)]
    lows = [float(-i) - 1.0 for i in range(30)]
    up, down, osc = aroon(highs, lows, period=10)
    assert up[15] == 0.0
    assert down[15] == 100.0
    assert osc[15] == -100.0


def test_aroon_short_window_returns_empty_lists() -> None:
    """`period >= n` cannot seed (need period + 1 bars)."""
    out = aroon([1.0, 2.0, 3.0], [0.0, 1.0, 2.0], period=10)
    assert out == ([], [], [])


def test_aroon_empty_input() -> None:
    assert aroon([], [], period=10) == ([], [], [])


def test_aroon_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        aroon([1.0, 2.0], [1.0], period=2)


def test_aroon_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        aroon([1.0, 2.0, 3.0], [0.0, 1.0, 2.0], period=0)
