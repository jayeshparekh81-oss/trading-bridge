"""Tests for :class:`app.services.indicators.macd.MacdIndicator`."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.indicator import IndicatorName, MacdParams
from app.services.indicators.macd import MacdIndicator
from tests.services.indicators.conftest import (
    load_expected_csv,
    load_input_csv,
    synthesise_candles,
)


_FIXTURES = Path(__file__).parent / "fixtures"


def test_name_is_macd() -> None:
    assert MacdIndicator().name == IndicatorName.MACD


def test_output_names() -> None:
    assert MacdIndicator().output_names == ("macd", "signal", "histogram")


def test_empty_returns_three_empty_arrays() -> None:
    out = MacdIndicator().compute([], MacdParams())
    assert out["macd"].size == 0
    assert out["signal"].size == 0
    assert out["histogram"].size == 0


def test_warmup_then_valid() -> None:
    """MACD warmup ≈ slow_length + signal_length - 1 = 26+9-1 = 34 positions."""
    candles = synthesise_candles(n=200)
    out = MacdIndicator().compute(candles, MacdParams())
    # First 25 positions are NaN at minimum (slow EMA warmup).
    assert all(math.isnan(v) for v in out["macd"][:25])
    # Once everything has warmed, all three series produce finite values.
    assert all(math.isfinite(v) for v in out["macd"][34:])
    assert all(math.isfinite(v) for v in out["signal"][34:])
    assert all(math.isfinite(v) for v in out["histogram"][34:])


def test_histogram_equals_macd_minus_signal() -> None:
    candles = synthesise_candles(n=200)
    out = MacdIndicator().compute(candles, MacdParams())
    for m, s, h in zip(
        out["macd"][34:], out["signal"][34:], out["histogram"][34:]
    ):
        assert abs(h - (m - s)) < 1e-9


@pytest.mark.parametrize("fast,slow,signal", [(12, 26, 9)])
def test_tradingview_result_match(
    fast: int, slow: int, signal: int
) -> None:
    candles = load_input_csv(_FIXTURES / "shared_input.csv")
    expected = load_expected_csv(_FIXTURES / "macd_expected.csv")
    out = MacdIndicator().compute(
        candles,
        MacdParams(fast_length=fast, slow_length=slow, signal_length=signal),
    )
    for name in ("macd", "signal", "histogram"):
        assert len(out[name]) == len(expected[name])
        for i, (got, want) in enumerate(
            zip(out[name].tolist(), expected[name])
        ):
            if want is None:
                assert math.isnan(got), f"{name}[{i}]: expected NaN"
            else:
                assert abs(got - want) < 1e-6, (
                    f"{name}[{i}]: expected {want}, got {got}"
                )


def test_nan_in_input_poisons_all_three_series() -> None:
    candles = synthesise_candles(n=120)
    poisoned = candles[50].model_construct(
        symbol=candles[50].symbol,
        timeframe=candles[50].timeframe,
        timestamp=candles[50].timestamp,
        open=candles[50].open,
        high=candles[50].high,
        low=candles[50].low,
        close=Decimal("NaN"),
        volume=candles[50].volume,
    )
    candles[50] = poisoned
    out = MacdIndicator().compute(candles, MacdParams())
    # All three series: NaN from position 50 onwards.
    for name in ("macd", "signal", "histogram"):
        assert all(math.isnan(v) for v in out[name][50:])
