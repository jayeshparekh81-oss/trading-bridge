"""Tests for :class:`app.services.indicators.rsi.RsiIndicator`."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.indicator import IndicatorName, RsiParams
from app.services.indicators.rsi import RsiIndicator
from tests.services.indicators.conftest import (
    load_expected_csv,
    load_input_csv,
    synthesise_candles,
)


_FIXTURES = Path(__file__).parent / "fixtures"


def test_name_is_rsi() -> None:
    assert RsiIndicator().name == IndicatorName.RSI


def test_output_names() -> None:
    assert RsiIndicator().output_names == ("value",)


def test_empty_returns_empty_array() -> None:
    out = RsiIndicator().compute([], RsiParams(length=14))
    assert out["value"].size == 0


def test_length_exceeds_input_all_nan() -> None:
    candles = synthesise_candles(n=5)
    out = RsiIndicator().compute(candles, RsiParams(length=14))["value"]
    assert all(math.isnan(v) for v in out)


def test_warmup_then_valid_and_bounded() -> None:
    """RSI(14) needs 14 deltas → first 14 positions NaN, then values in [0, 100]."""
    candles = synthesise_candles(n=200)
    out = RsiIndicator().compute(candles, RsiParams(length=14))["value"]
    assert all(math.isnan(v) for v in out[:14])
    assert all(0.0 <= v <= 100.0 for v in out[14:] if math.isfinite(v))


def test_strictly_rising_input_yields_high_rsi() -> None:
    """A monotonically rising series → RSI approaches 100 (no losses)."""
    from datetime import timedelta

    base = synthesise_candles(n=1)[0].timestamp
    from app.schemas.candle import Candle, Timeframe

    candles = [
        Candle(
            symbol="X",
            timeframe=Timeframe.FIVE_MIN,
            timestamp=base + timedelta(minutes=5 * i),
            open=Decimal("1"),
            high=Decimal(str(101 + i)),
            low=Decimal("1"),
            close=Decimal(str(100 + i)),
            volume=0,
        )
        for i in range(50)
    ]
    out = RsiIndicator().compute(candles, RsiParams(length=14))["value"]
    # Pure-gain series → average_loss = 0 → RSI = 100.
    assert abs(out[-1] - 100.0) < 1e-6


@pytest.mark.parametrize("length", [14])
def test_tradingview_result_match(length: int) -> None:
    candles = load_input_csv(_FIXTURES / "shared_input.csv")
    expected = load_expected_csv(_FIXTURES / "rsi_expected.csv")
    out = RsiIndicator().compute(candles, RsiParams(length=length))["value"]
    assert len(out) == len(expected["value"])
    for i, (got, want) in enumerate(zip(out.tolist(), expected["value"])):
        if want is None:
            assert math.isnan(got)
        else:
            assert abs(got - want) < 1e-6, (
                f"position {i}: expected {want}, got {got}"
            )


def test_nan_in_input_poisons_subsequent_output() -> None:
    candles = synthesise_candles(n=60)
    poisoned = candles[30].model_construct(
        symbol=candles[30].symbol,
        timeframe=candles[30].timeframe,
        timestamp=candles[30].timestamp,
        open=candles[30].open,
        high=candles[30].high,
        low=candles[30].low,
        close=Decimal("NaN"),
        volume=candles[30].volume,
    )
    candles[30] = poisoned
    out = RsiIndicator().compute(candles, RsiParams(length=14))["value"]
    # Positions before the NaN: finite past warmup (14..29).
    assert all(math.isfinite(v) for v in out[14:30])
    # Positions from NaN onward: NaN (Wilder smoothing is recursive).
    assert all(math.isnan(v) for v in out[30:])
