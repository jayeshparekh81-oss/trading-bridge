"""VWAP calculation tests.

Phase 1 ships **anchored-at-start** VWAP (cumulative from index 0); the
Phase 2/3 backtest engine will introduce session-anchored variants.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.vwap import vwap
from tests.strategy_engine.fixtures.ohlcv_sample import CLOSES, HIGHS, LOWS, VOLUMES


def test_vwap_first_bar_equals_typical_price() -> None:
    """At i=0, VWAP = typical_price * volume / volume = typical_price."""
    out = vwap(HIGHS, LOWS, CLOSES, VOLUMES)
    expected_first = (HIGHS[0] + LOWS[0] + CLOSES[0]) / 3
    assert out[0] == pytest.approx(expected_first)


def test_vwap_constant_typical_price_is_constant() -> None:
    """If every bar has the same typical price, cumulative VWAP equals it."""
    n = 6
    h = [10.0] * n
    lo = [9.0] * n
    c = [9.0] * n
    v = [100.0, 200.0, 300.0, 0.0, 50.0, 25.0]  # any non-degenerate volume
    out = vwap(h, lo, c, v)
    expected = (10.0 + 9.0 + 9.0) / 3
    for value in out:
        assert value == pytest.approx(expected)


def test_vwap_zero_volume_warmup_returns_none() -> None:
    """Bars before the first non-zero volume have no defined VWAP."""
    out = vwap([10, 11], [9, 10], [9.5, 10.5], [0, 0])
    assert out == [None, None]


def test_vwap_zero_then_volume_starts_defined() -> None:
    out = vwap([10, 11, 12], [9, 10, 11], [9.5, 10.5, 11.5], [0, 100, 50])
    assert out[0] is None
    assert out[1] is not None
    assert out[2] is not None


def test_vwap_empty_input() -> None:
    assert vwap([], [], [], []) == []


def test_vwap_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        vwap([1, 2], [1], [1, 2], [10, 20])


def test_vwap_output_length_matches_input_length() -> None:
    out = vwap(HIGHS, LOWS, CLOSES, VOLUMES)
    assert len(out) == len(HIGHS)
