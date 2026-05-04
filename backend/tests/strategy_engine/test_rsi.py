"""RSI calculation tests.

Canonical vector source:
    J. Welles Wilder Jr., "New Concepts in Technical Trading Systems"
    (1978), Table III "RSI Calculation". The first ~6 RSI values
    Wilder publishes for his 14-period example — reproduced via the
    fixture in :mod:`tests.strategy_engine.fixtures.ohlcv_sample`.

Wilder rounded to two decimals in the book; we compare with a small
absolute tolerance to absorb that.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.rsi import rsi
from tests.strategy_engine.fixtures.ohlcv_sample import (
    MONOTONIC_UP_CLOSES,
    WILDER_RSI_CLOSES,
)


def test_rsi_wilder_first_value_canonical() -> None:
    """Wilder publishes RSI=70.53 at the first defined index (i=14).

    Wilder's worked example rounds avg_gain / avg_loss to two decimals at
    every step of the table, and that rounding compounds across 14
    iterations. Full-precision arithmetic on the same close column yields
    ~70.46. The 0.10 tolerance below absorbs that documented rounding
    drift while still catching any genuine algorithmic bug — even a
    one-bar recursion error would push the value far outside the band.
    """
    out = rsi(WILDER_RSI_CLOSES, 14)
    assert out[14] is not None
    assert out[14] == pytest.approx(70.53, abs=0.10)


def test_rsi_warmup_positions_are_none() -> None:
    out = rsi(WILDER_RSI_CLOSES, 14)
    assert all(v is None for v in out[:14])
    assert out[14] is not None


def test_rsi_output_length_matches_input_length() -> None:
    out = rsi(WILDER_RSI_CLOSES, 14)
    assert len(out) == len(WILDER_RSI_CLOSES)


def test_rsi_monotonic_up_saturates_at_100() -> None:
    """Strict-up series: avg_loss = 0 -> RSI must clip to 100."""
    out = rsi(MONOTONIC_UP_CLOSES, 5)
    # First defined RSI is at index 5; check several positions in.
    defined = [v for v in out if v is not None]
    assert defined  # non-empty
    assert all(v == 100.0 for v in defined)


def test_rsi_monotonic_down_saturates_at_zero() -> None:
    """Strict-down series: avg_gain = 0 -> RSI must clip to 0.

    The function returns 50.0 only when *both* avg_gain and avg_loss
    are zero — which only happens with a perfectly flat series.
    """
    closes = list(reversed(MONOTONIC_UP_CLOSES))
    out = rsi(closes, 5)
    defined = [v for v in out if v is not None]
    assert defined
    assert all(v == 0.0 for v in defined)


def test_rsi_flat_series_returns_fifty() -> None:
    """No moves at all: avg_gain == avg_loss == 0 -> the convention is 50."""
    out = rsi([10.0] * 10, 4)
    defined = [v for v in out if v is not None]
    assert defined
    assert all(v == 50.0 for v in defined)


def test_rsi_empty_input() -> None:
    assert rsi([], 14) == []


def test_rsi_period_too_large_returns_empty() -> None:
    """Need ``period + 1`` prices to seed; len == period is one short."""
    assert rsi([1.0, 2.0, 3.0], 3) == []


def test_rsi_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        rsi([1, 2, 3, 4, 5], 0)
