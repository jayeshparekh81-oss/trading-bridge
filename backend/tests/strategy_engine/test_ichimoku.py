"""Ichimoku basic (Tenkan + Kijun) calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.ichimoku import ichimoku


def test_ichimoku_seeds_at_each_period_minus_one() -> None:
    """Tenkan defined from index tenkan_period - 1; Kijun from kijun_period - 1."""
    n = 40
    highs = [float(i) for i in range(n)]
    lows = [float(i) - 1.0 for i in range(n)]
    tenkan, kijun = ichimoku(highs, lows, tenkan_period=9, kijun_period=26)
    assert tenkan[7] is None
    assert tenkan[8] is not None
    assert kijun[24] is None
    assert kijun[25] is not None


def test_ichimoku_constant_series_is_constant_midline() -> None:
    """Flat highs/lows → midline = (constant + constant) / 2 = constant."""
    tenkan, kijun = ichimoku([5.0] * 30, [3.0] * 30, tenkan_period=9, kijun_period=26)
    assert tenkan[8] == 4.0
    assert kijun[25] == 4.0


def test_ichimoku_rising_series_kijun_lags_tenkan() -> None:
    """In a clean uptrend the longer-window Kijun lags below Tenkan."""
    n = 60
    highs = [float(i) for i in range(n)]
    lows = [float(i) - 1.0 for i in range(n)]
    tenkan, kijun = ichimoku(highs, lows, tenkan_period=9, kijun_period=26)
    for i in range(25, n):
        assert tenkan[i] is not None and kijun[i] is not None
        assert tenkan[i] > kijun[i]  # type: ignore[operator]


def test_ichimoku_output_length_parity() -> None:
    tenkan, kijun = ichimoku([1.0] * 40, [0.5] * 40)
    assert len(tenkan) == 40
    assert len(kijun) == 40


def test_ichimoku_short_input_kijun_remains_none() -> None:
    """Tenkan can seed when 9 ≤ n < 26; Kijun stays all None."""
    tenkan, kijun = ichimoku([float(i) for i in range(15)], [float(i) - 1 for i in range(15)])
    assert tenkan[8] is not None
    assert all(v is None for v in kijun)


def test_ichimoku_empty_input() -> None:
    assert ichimoku([], []) == ([], [])


def test_ichimoku_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        ichimoku([1.0, 2.0], [1.0])


def test_ichimoku_rejects_unordered_periods() -> None:
    with pytest.raises(ValueError):
        ichimoku([1.0] * 30, [0.5] * 30, tenkan_period=26, kijun_period=9)


def test_ichimoku_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        ichimoku([1.0] * 30, [0.5] * 30, tenkan_period=0, kijun_period=26)
