"""Chaikin Money Flow calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.cmf import cmf


def test_cmf_close_at_top_of_range_is_one() -> None:
    """Every bar closes at its high → MFM = +1 → CMF = +1."""
    highs = [10.0] * 30
    lows = [9.0] * 30
    closes = [10.0] * 30  # at the top of the bar's range
    volumes = [100.0] * 30
    out = cmf(highs, lows, closes, volumes, period=20)
    assert out[19] == 1.0
    assert out[-1] == 1.0


def test_cmf_close_at_bottom_of_range_is_minus_one() -> None:
    highs = [10.0] * 30
    lows = [9.0] * 30
    closes = [9.0] * 30
    volumes = [100.0] * 30
    out = cmf(highs, lows, closes, volumes, period=20)
    assert out[-1] == -1.0


def test_cmf_flat_bars_yield_zero() -> None:
    """high == low → MFM defined as 0 → CMF zero everywhere."""
    flat = [5.0] * 30
    out = cmf(flat, flat, flat, [100.0] * 30, period=20)
    for v in out:
        if v is not None:
            assert v == 0.0


def test_cmf_output_length_parity_and_seed() -> None:
    highs = [10.0] * 30
    lows = [9.0] * 30
    closes = [9.5] * 30
    volumes = [100.0] * 30
    out = cmf(highs, lows, closes, volumes, period=20)
    assert len(out) == 30
    assert out[18] is None
    assert out[19] is not None


def test_cmf_short_input_returns_empty() -> None:
    assert cmf([1.0] * 5, [0.0] * 5, [0.5] * 5, [10.0] * 5, period=20) == []


def test_cmf_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        cmf([1.0, 2.0], [0.0], [0.5, 1.0], [10.0, 10.0], period=2)


def test_cmf_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        cmf([1.0] * 5, [0.0] * 5, [0.5] * 5, [10.0] * 5, period=0)


def test_cmf_zero_volume_window_yields_zero() -> None:
    """sum(volumes) == 0 → CMF defined as 0 (not NaN)."""
    out = cmf([1.0] * 25, [0.0] * 25, [0.5] * 25, [0.0] * 25, period=20)
    assert out[-1] == 0.0
