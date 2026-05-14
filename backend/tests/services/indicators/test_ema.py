"""Tests for :class:`app.services.indicators.ema.EmaIndicator`."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.candle import Candle, Timeframe
from app.schemas.indicator import EmaParams, IndicatorName
from app.services.indicators.ema import EmaIndicator
from tests.services.indicators.conftest import (
    load_expected_csv,
    load_input_csv,
    synthesise_candles,
)


_FIXTURES = Path(__file__).parent / "fixtures"


def test_name_is_ema() -> None:
    assert EmaIndicator().name == IndicatorName.EMA


def test_output_names() -> None:
    assert EmaIndicator().output_names == ("value",)


def test_empty_returns_empty_array() -> None:
    out = EmaIndicator().compute([], EmaParams(length=20))
    assert out["value"].size == 0


def test_length_exceeds_input_all_nan() -> None:
    candles = synthesise_candles(n=5)
    out = EmaIndicator().compute(candles, EmaParams(length=50))["value"]
    assert all(math.isnan(v) for v in out)


def test_warmup_then_valid() -> None:
    candles = synthesise_candles(n=200)
    out = EmaIndicator().compute(candles, EmaParams(length=20))["value"]
    # TA-Lib EMA seeds via SMA, so first ``length - 1`` are NaN.
    assert all(math.isnan(v) for v in out[:19])
    assert all(math.isfinite(v) for v in out[19:])


def test_ema_approaches_constant_for_flat_input() -> None:
    candles = [
        Candle(
            symbol="X",
            timeframe=Timeframe.FIVE_MIN,
            timestamp=synthesise_candles(n=1)[0].timestamp,
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=0,
        )
        for _ in range(50)
    ]
    out = EmaIndicator().compute(candles, EmaParams(length=10))["value"]
    assert all(abs(v - 100.0) < 1e-9 for v in out[9:])


@pytest.mark.parametrize("length", [20])
def test_tradingview_result_match(length: int) -> None:
    candles = load_input_csv(_FIXTURES / "shared_input.csv")
    expected = load_expected_csv(_FIXTURES / "ema_expected.csv")
    out = EmaIndicator().compute(candles, EmaParams(length=length))["value"]
    assert len(out) == len(expected["value"])
    for i, (got, want) in enumerate(zip(out.tolist(), expected["value"])):
        if want is None:
            assert math.isnan(got), f"position {i}: expected NaN, got {got}"
        else:
            assert abs(got - want) < 1e-6, (
                f"position {i}: expected {want}, got {got}"
            )


def test_nan_in_input_poisons_subsequent_output() -> None:
    """TA-Lib's EMA is recursive (``ema[t] = α*close[t] + (1-α)*ema[t-1]``).
    Once NaN enters the recursion the previous-state propagates NaN
    forever. Same flagged Pine divergence as SMA."""
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
    out = EmaIndicator().compute(candles, EmaParams(length=10))["value"]
    assert all(math.isfinite(v) for v in out[9:30])
    assert all(math.isnan(v) for v in out[30:])
