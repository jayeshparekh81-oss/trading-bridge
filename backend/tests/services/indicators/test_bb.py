"""Tests for :class:`app.services.indicators.bb.BollingerBandsIndicator`."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.indicator import BbParams, IndicatorName
from app.services.indicators.bb import BollingerBandsIndicator
from tests.services.indicators.conftest import (
    load_expected_csv,
    load_input_csv,
    synthesise_candles,
)


_FIXTURES = Path(__file__).parent / "fixtures"


def test_name_is_bb() -> None:
    assert BollingerBandsIndicator().name == IndicatorName.BB


def test_output_names() -> None:
    assert BollingerBandsIndicator().output_names == ("upper", "middle", "lower")


def test_empty_returns_three_empty_arrays() -> None:
    out = BollingerBandsIndicator().compute([], BbParams())
    assert out["upper"].size == 0
    assert out["middle"].size == 0
    assert out["lower"].size == 0


def test_warmup_then_valid() -> None:
    candles = synthesise_candles(n=200)
    out = BollingerBandsIndicator().compute(candles, BbParams())
    assert all(math.isnan(v) for v in out["upper"][:19])
    assert all(math.isfinite(v) for v in out["upper"][19:])
    assert all(math.isfinite(v) for v in out["middle"][19:])
    assert all(math.isfinite(v) for v in out["lower"][19:])


def test_band_ordering_upper_ge_middle_ge_lower() -> None:
    candles = synthesise_candles(n=200)
    out = BollingerBandsIndicator().compute(candles, BbParams())
    for u, m, l in zip(
        out["upper"][19:], out["middle"][19:], out["lower"][19:]
    ):
        assert u >= m >= l - 1e-9


def test_flat_input_yields_zero_band_width() -> None:
    """Constant series → stddev = 0 → upper == middle == lower."""
    from app.schemas.candle import Candle, Timeframe
    from datetime import timedelta

    base = synthesise_candles(n=1)[0].timestamp
    candles = [
        Candle(
            symbol="X",
            timeframe=Timeframe.FIVE_MIN,
            timestamp=base + timedelta(minutes=5 * i),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=0,
        )
        for i in range(50)
    ]
    out = BollingerBandsIndicator().compute(candles, BbParams(length=20))
    for u, m, l in zip(out["upper"][19:], out["middle"][19:], out["lower"][19:]):
        assert abs(u - 100.0) < 1e-9
        assert abs(m - 100.0) < 1e-9
        assert abs(l - 100.0) < 1e-9


def test_pine_compat_correction_applied() -> None:
    """ACTION 1 verification: BB output uses sample stddev (sqrt(N/(N-1))
    wider than TA-Lib's raw biased output)."""
    import math
    import talib as _talib
    import numpy as _np

    candles = synthesise_candles(n=100)
    closes = _np.array([float(c.close) for c in candles], dtype=_np.float64)
    raw_upper, raw_middle, raw_lower = _talib.BBANDS(
        closes, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0
    )
    out = BollingerBandsIndicator().compute(candles, BbParams(length=20))
    factor = math.sqrt(20 / 19)
    # Tail position has both raw and corrected values available.
    raw_half_width = raw_upper[-1] - raw_middle[-1]
    pine_half_width = out["upper"][-1] - out["middle"][-1]
    assert abs(pine_half_width - raw_half_width * factor) < 1e-9
    # Middle band unchanged by the correction.
    assert abs(out["middle"][-1] - raw_middle[-1]) < 1e-9


def test_length_1_rejected_by_schema() -> None:
    """``BbParams.length`` is constrained ``ge=2`` because TA-Lib's
    BBANDS rejects length=1 (sample stddev is undefined). Validation
    must reject at the Pydantic boundary, NOT inside compute()."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BbParams(length=1)


def test_stddev_multiplier_scales_band_width() -> None:
    """Doubling stddev_multiplier doubles the (upper - middle) distance."""
    candles = synthesise_candles(n=100)
    bb_1 = BollingerBandsIndicator().compute(
        candles, BbParams(length=20, stddev_multiplier=1.0)
    )
    bb_2 = BollingerBandsIndicator().compute(
        candles, BbParams(length=20, stddev_multiplier=2.0)
    )
    for i in range(19, 100):
        width_1 = bb_1["upper"][i] - bb_1["middle"][i]
        width_2 = bb_2["upper"][i] - bb_2["middle"][i]
        assert abs(width_2 - 2.0 * width_1) < 1e-9


@pytest.mark.parametrize("length,mult", [(20, 2.0)])
def test_tradingview_result_match(length: int, mult: float) -> None:
    candles = load_input_csv(_FIXTURES / "shared_input.csv")
    expected = load_expected_csv(_FIXTURES / "bb_expected.csv")
    out = BollingerBandsIndicator().compute(
        candles, BbParams(length=length, stddev_multiplier=mult)
    )
    for name in ("upper", "middle", "lower"):
        for i, (got, want) in enumerate(zip(out[name].tolist(), expected[name])):
            if want is None:
                assert math.isnan(got)
            else:
                assert abs(got - want) < 1e-6


def test_nan_in_input_poisons_all_three_bands() -> None:
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
    out = BollingerBandsIndicator().compute(candles, BbParams(length=10))
    for name in ("upper", "middle", "lower"):
        assert all(math.isnan(v) for v in out[name][30:])
