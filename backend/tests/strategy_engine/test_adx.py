"""ADX / DMI calculation tests.

Each test pins one observable property of the Wilder pipeline:
length parity, the +DI / -DI seed index, the ADX seed index (which
needs an extra ``period`` bars beyond the DMI seed), and the strong-
trend property (rising series → ADX climbs, +DI dominates -DI).
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.adx import adx


def _series(length: int, start: float = 100.0, slope: float = 1.0) -> tuple[
    list[float], list[float], list[float]
]:
    """Strictly rising trend: each bar prints +slope from the prior."""
    closes = [start + slope * i for i in range(length)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    return highs, lows, closes


def test_adx_returns_three_padded_lists_of_input_length() -> None:
    highs, lows, closes = _series(60)
    adx_line, plus_di, minus_di = adx(highs, lows, closes, period=14)
    assert len(adx_line) == 60
    assert len(plus_di) == 60
    assert len(minus_di) == 60


def test_adx_plus_di_seeds_at_period_index() -> None:
    """+DI / -DI are first defined at index `period` (sum-seeded)."""
    highs, lows, closes = _series(60)
    _, plus_di, minus_di = adx(highs, lows, closes, period=14)
    assert plus_di[13] is None
    assert plus_di[14] is not None
    assert minus_di[13] is None
    assert minus_di[14] is not None


def test_adx_line_seeds_at_two_period_minus_one() -> None:
    """ADX needs `period` more DX values; first defined index is 2*period - 1."""
    highs, lows, closes = _series(60)
    adx_line, _, _ = adx(highs, lows, closes, period=14)
    assert adx_line[2 * 14 - 2] is None
    assert adx_line[2 * 14 - 1] is not None


def test_adx_strong_uptrend_dominates_plus_di_over_minus_di() -> None:
    """In a clean uptrend +DI must be > -DI for every defined bar."""
    highs, lows, closes = _series(80)
    _, plus_di, minus_di = adx(highs, lows, closes, period=14)
    for p, m in zip(plus_di[14:], minus_di[14:], strict=True):
        assert p is not None and m is not None
        assert p > m


def test_adx_short_input_returns_padding_only() -> None:
    """When n <= period the +DI / -DI / ADX are all None of length n."""
    highs, lows, closes = _series(10)
    adx_line, plus_di, minus_di = adx(highs, lows, closes, period=14)
    assert adx_line == [None] * 10
    assert plus_di == [None] * 10
    assert minus_di == [None] * 10


def test_adx_empty_input_returns_three_empty_lists() -> None:
    assert adx([], [], [], period=14) == ([], [], [])


def test_adx_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        adx([1.0, 2.0], [1.0], [1.0, 2.0])


def test_adx_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        adx([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], period=0)
