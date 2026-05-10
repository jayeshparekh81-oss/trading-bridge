"""Force Index calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.force_index import force_index


def test_force_index_uptrend_is_positive() -> None:
    closes = [100.0 + i for i in range(40)]
    volumes = [1000.0] * 40
    out = force_index(closes, volumes, period=13)
    last = out[-1]
    assert last is not None
    assert last > 0


def test_force_index_downtrend_is_negative() -> None:
    closes = [100.0 - i for i in range(40)]
    volumes = [1000.0] * 40
    out = force_index(closes, volumes, period=13)
    last = out[-1]
    assert last is not None
    assert last < 0


def test_force_index_flat_market_is_zero() -> None:
    out = force_index([100.0] * 40, [1000.0] * 40, period=13)
    for v in out:
        if v is not None:
            assert v == 0.0


def test_force_index_index_zero_is_none() -> None:
    """Bar 0 has no prior close — always None."""
    out = force_index([100.0] * 40, [1000.0] * 40, period=13)
    assert out[0] is None


def test_force_index_output_length_parity() -> None:
    out = force_index([100.0] * 40, [1000.0] * 40, period=13)
    assert len(out) == 40


def test_force_index_short_input_returns_empty() -> None:
    assert force_index([1.0, 2.0], [10.0, 10.0], period=13) == []


def test_force_index_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        force_index([1.0, 2.0], [10.0], period=2)


def test_force_index_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        force_index([1.0, 2.0, 3.0], [10.0, 10.0, 10.0], period=0)
