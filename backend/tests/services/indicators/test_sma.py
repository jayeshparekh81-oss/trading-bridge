"""Tests for :class:`app.services.indicators.sma.SmaIndicator`."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from app.schemas.candle import Candle, Timeframe
from app.schemas.indicator import IndicatorName, SmaParams
from app.services.indicators.sma import SmaIndicator
from tests.services.indicators.conftest import (
    load_expected_csv,
    load_input_csv,
    synthesise_candles,
)


# ═══════════════════════════════════════════════════════════════════════
# Identity + protocol shape
# ═══════════════════════════════════════════════════════════════════════


def test_name_is_sma() -> None:
    assert SmaIndicator().name == IndicatorName.SMA


def test_output_names_single_value() -> None:
    assert SmaIndicator().output_names == ("value",)


# ═══════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════


def test_empty_candles_returns_empty_array() -> None:
    out = SmaIndicator().compute([], SmaParams(length=20))
    assert out["value"].size == 0


def test_single_candle_all_nan() -> None:
    candles = synthesise_candles(n=1)
    out = SmaIndicator().compute(candles, SmaParams(length=20))
    assert out["value"].shape == (1,)
    assert math.isnan(out["value"][0])


def test_length_exceeds_input_all_nan() -> None:
    candles = synthesise_candles(n=10)
    out = SmaIndicator().compute(candles, SmaParams(length=50))
    assert all(math.isnan(v) for v in out["value"])


def test_warmup_period_is_nan_then_valid() -> None:
    """SMA(20) warmup = 19 NaN positions, then valid values."""
    candles = synthesise_candles(n=200)
    out = SmaIndicator().compute(candles, SmaParams(length=20))["value"]
    # Positions 0..18 are warmup → NaN
    assert all(math.isnan(v) for v in out[:19])
    # Position 19 onwards → finite
    assert all(math.isfinite(v) for v in out[19:])


def test_constant_input_yields_constant_output() -> None:
    """SMA of a flat series = the flat value (after warmup)."""
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
        for _ in range(30)
    ]
    out = SmaIndicator().compute(candles, SmaParams(length=5))["value"]
    assert all(abs(v - 100.0) < 1e-9 for v in out[4:])


# ═══════════════════════════════════════════════════════════════════════
# TradingView result-match (T1)
# ═══════════════════════════════════════════════════════════════════════
#
# The expected CSV ships TA-Lib-derived values; pre-launch the
# operator replaces it with TradingView Pine ``ta.sma`` capture.
# Tolerance 1e-6 absolute, parametrised over a single named case
# so the matrix is easy to extend with additional symbol/timeframe
# fixtures later.


_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("length", [20])
def test_tradingview_result_match(length: int) -> None:
    input_csv = _FIXTURES / "shared_input.csv"
    expected_csv = _FIXTURES / "sma_expected.csv"
    candles = load_input_csv(input_csv)
    expected = load_expected_csv(expected_csv)

    out = SmaIndicator().compute(candles, SmaParams(length=length))["value"]

    assert len(out) == len(expected["value"])
    for i, (got, want) in enumerate(zip(out.tolist(), expected["value"])):
        if want is None:
            assert math.isnan(got), f"position {i}: expected NaN, got {got}"
        else:
            assert abs(got - want) < 1e-6, (
                f"position {i}: expected {want}, got {got}, "
                f"diff {abs(got - want)}"
            )


# ═══════════════════════════════════════════════════════════════════════
# NaN propagation (T2)
# ═══════════════════════════════════════════════════════════════════════


def test_nan_in_input_poisons_subsequent_output() -> None:
    """NaN propagation contract for TA-Lib's sliding-sum SMA.

    **Behaviour-spec deviation:** TA-Lib's SMA implementation maintains
    a rolling sum (``sum += close[t]; sum -= close[t-length]``). Once
    NaN enters the accumulator, it persists indefinitely — ``NaN - NaN``
    is still ``NaN``. So the output remains NaN for every position from
    the NaN-input bar through the end of the input series, **not** just
    for ``length`` positions.

    Pine Script's ``ta.sma`` recovers after the smoothing window
    clears. The Day-6 brief specified Pine-style recovery; we ship
    TA-Lib's behaviour per the locked architecture (TA-Lib defaults
    are industry-standard; deviations flagged). Documented in
    ``PATCH_INSTRUCTIONS_INDICATORS.md`` under "NaN behaviour gap vs
    Pine Script".
    """
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

    out = SmaIndicator().compute(candles, SmaParams(length=10))["value"]

    # Before the poisoned position: warmup NaN (0..8), then valid (9..29).
    assert all(math.isfinite(v) for v in out[9:30])
    # From poisoned position to end of series: NaN (sliding-sum poisoning).
    assert all(math.isnan(v) for v in out[30:])


# ═══════════════════════════════════════════════════════════════════════
# Hand-verifiable case
# ═══════════════════════════════════════════════════════════════════════


def test_hand_computed_consecutive_integers() -> None:
    """SMA(5) of close = [1..30] → last value = mean(26..30) = 28."""
    base = synthesise_candles(n=1)[0].timestamp
    from datetime import timedelta

    candles = [
        Candle(
            symbol="X",
            timeframe=Timeframe.FIVE_MIN,
            timestamp=base + timedelta(minutes=5 * i),
            open=Decimal("1"),
            high=Decimal(str(i + 1)),
            low=Decimal("1"),
            close=Decimal(str(i + 1)),
            volume=0,
        )
        for i in range(30)
    ]
    out = SmaIndicator().compute(candles, SmaParams(length=5))["value"]
    # Last position: mean of [26,27,28,29,30] = 28.0.
    assert abs(out[-1] - 28.0) < 1e-9
