"""TRIX calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.trix import trix


def test_trix_constant_series_is_zero_once_warmed_up() -> None:
    """A flat series triple-smooths to itself; the rate of change is 0."""
    out = trix([5.0] * 60, period=5)
    # Find the first defined value and assert from there.
    first_defined = next(i for i, v in enumerate(out) if v is not None)
    for v in out[first_defined:]:
        assert v == 0.0


def test_trix_uptrend_is_positive() -> None:
    """A monotone-rising series produces a positive TRIX (smoothed > prev)."""
    values = [100.0 + i for i in range(60)]
    out = trix(values, period=5)
    first_defined = next(i for i, v in enumerate(out) if v is not None)
    for v in out[first_defined:]:
        assert v is not None
        assert v > 0


def test_trix_downtrend_is_negative() -> None:
    values = [100.0 - i for i in range(60)]
    out = trix(values, period=5)
    first_defined = next(i for i, v in enumerate(out) if v is not None)
    for v in out[first_defined:]:
        assert v is not None
        assert v < 0


def test_trix_output_length_parity() -> None:
    out = trix([1.0] * 60, period=5)
    assert len(out) == 60


def test_trix_short_input_returns_empty() -> None:
    """Insufficient bars to seed three EMAs and take a difference."""
    assert trix([1.0, 2.0, 3.0], period=5) == []


def test_trix_empty_input() -> None:
    assert trix([], period=5) == []


def test_trix_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        trix([1.0, 2.0, 3.0], period=0)
