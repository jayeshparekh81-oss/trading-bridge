"""Schema tests for the Candle / PriceSource boundary types."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.strategy_engine.schema.ohlcv import Candle, PriceSource


def _make_candle(**overrides: object) -> Candle:
    base: dict[str, object] = {
        "timestamp": datetime(2026, 1, 2, 9, 15, tzinfo=UTC),
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 103.0,
        "volume": 1500.0,
    }
    base.update(overrides)
    return Candle(**base)  # type: ignore[arg-type]


def test_candle_basic_construction() -> None:
    c = _make_candle()
    assert c.high == 105.0
    assert c.volume == 1500.0


def test_candle_low_above_high_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _make_candle(low=200, high=150)
    assert "low" in str(excinfo.value)


def test_candle_close_above_high_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_candle(close=999)


def test_candle_open_below_low_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_candle(open=0.5, low=10, high=20, close=15)


def test_candle_negative_volume_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_candle(volume=-1)


def test_candle_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        _make_candle(unexpected=1)


def test_candle_is_frozen() -> None:
    c = _make_candle()
    with pytest.raises((TypeError, ValueError)):
        c.close = 999.0  # type: ignore[misc]


def test_candle_price_returns_each_source() -> None:
    c = _make_candle(open=100, high=110, low=90, close=105, volume=1000)
    assert c.price(PriceSource.OPEN) == 100
    assert c.price(PriceSource.HIGH) == 110
    assert c.price(PriceSource.LOW) == 90
    assert c.price(PriceSource.CLOSE) == 105
    assert c.price(PriceSource.VOLUME) == 1000
    assert c.price(PriceSource.HL2) == pytest.approx((110 + 90) / 2)
    assert c.price(PriceSource.HLC3) == pytest.approx((110 + 90 + 105) / 3)
    assert c.price(PriceSource.OHLC4) == pytest.approx((100 + 110 + 90 + 105) / 4)
