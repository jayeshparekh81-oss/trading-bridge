"""Tests for ``app.services.historical_candles.schema_bridge``.

Pure-Python tests — no DB, no I/O. Cover all four bridge functions plus
the load-bearing Decimal↔float round-trip property: prices that flow
ORM → engine → ORM must come back as the same Decimal value, even
through the IEEE-754 float layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db.models.historical_candle import HistoricalCandle
from app.schemas.candle import Candle as ChartCandle
from app.schemas.candle import Timeframe
from app.services.historical_candles.schema_bridge import (
    chart_candle_to_orm,
    engine_candle_to_orm,
    orm_to_chart_candle,
    orm_to_engine_candle,
)
from app.strategy_engine.schema.ohlcv import Candle as EngineCandle

_TS = datetime(2026, 6, 12, 9, 15, tzinfo=UTC)


def _make_orm(
    *,
    symbol: str = "RELIANCE",
    exchange: str = "NSE_EQ",
    timeframe: str = "5m",
    timestamp: datetime = _TS,
    open_: Decimal = Decimal("1234.5600"),
    high: Decimal = Decimal("1240.0000"),
    low: Decimal = Decimal("1230.0000"),
    close: Decimal = Decimal("1238.7500"),
    volume: int = 12345,
    dhan_security_id: str = "2885",
) -> HistoricalCandle:
    return HistoricalCandle(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        dhan_security_id=dhan_security_id,
    )


# ═══════════════════════════════════════════════════════════════════════
# orm_to_chart_candle
# ═══════════════════════════════════════════════════════════════════════


def test_orm_to_chart_candle__decimal_preserved_verbatim() -> None:
    orm = _make_orm(open_=Decimal("1234.5678"), close=Decimal("1239.9999"))
    chart = orm_to_chart_candle(orm)
    assert chart.open == Decimal("1234.5678")
    assert chart.close == Decimal("1239.9999")
    assert isinstance(chart.open, Decimal)


def test_orm_to_chart_candle__timeframe_string_to_enum() -> None:
    orm = _make_orm(timeframe="15m")
    chart = orm_to_chart_candle(orm)
    assert chart.timeframe is Timeframe.FIFTEEN_MIN


def test_orm_to_chart_candle__symbol_and_timestamp_passthrough() -> None:
    orm = _make_orm(symbol="HDFCBANK", timestamp=_TS)
    chart = orm_to_chart_candle(orm)
    assert chart.symbol == "HDFCBANK"
    assert chart.timestamp == _TS
    assert chart.volume == 12345


# ═══════════════════════════════════════════════════════════════════════
# chart_candle_to_orm
# ═══════════════════════════════════════════════════════════════════════


def _chart() -> ChartCandle:
    return ChartCandle(
        symbol="RELIANCE",
        timeframe=Timeframe.FIVE_MIN,
        timestamp=_TS,
        open=Decimal("1234.5600"),
        high=Decimal("1240.0000"),
        low=Decimal("1230.0000"),
        close=Decimal("1238.7500"),
        volume=12345,
    )


def test_chart_candle_to_orm__provenance_fields_set() -> None:
    user_id = uuid.uuid4()
    orm = chart_candle_to_orm(
        _chart(),
        exchange="NSE_EQ",
        dhan_security_id="2885",
        fetched_by_user_id=user_id,
    )
    assert orm.symbol == "RELIANCE"
    assert orm.exchange == "NSE_EQ"
    assert orm.timeframe == "5m"
    assert orm.dhan_security_id == "2885"
    assert orm.fetched_by_user_id == user_id
    assert orm.source == "dhan_v2_historical"  # default


def test_chart_candle_to_orm__custom_source_overrides_default() -> None:
    orm = chart_candle_to_orm(
        _chart(),
        exchange="NSE_EQ",
        dhan_security_id="2885",
        source="dhan_v2_backfill_replay",
    )
    assert orm.source == "dhan_v2_backfill_replay"


def test_chart_candle_to_orm__fetched_by_user_id_optional() -> None:
    orm = chart_candle_to_orm(_chart(), exchange="NSE_EQ", dhan_security_id="2885")
    assert orm.fetched_by_user_id is None


# ═══════════════════════════════════════════════════════════════════════
# orm_to_engine_candle  — the float-via-str() conversion
# ═══════════════════════════════════════════════════════════════════════


def test_orm_to_engine_candle__decimal_to_float_via_str() -> None:
    orm = _make_orm(
        open_=Decimal("42.05"),
        high=Decimal("42.99"),
        low=Decimal("41.50"),
        close=Decimal("42.80"),
    )
    engine = orm_to_engine_candle(orm)
    # The naive float(Decimal('42.05')) is also 42.05 on cpython, but
    # the str() route is the documented contract — assert the value.
    assert engine.open == 42.05
    assert isinstance(engine.open, float)


def test_orm_to_engine_candle__paise_precision_round_trip() -> None:
    orm = _make_orm(close=Decimal("1234.5600"))
    engine = orm_to_engine_candle(orm)
    # 1234.5600 stored, becomes 1234.56 in float (trailing zero dropped).
    assert engine.close == 1234.56


def test_orm_to_engine_candle__volume_int_to_float() -> None:
    orm = _make_orm(volume=987654)
    engine = orm_to_engine_candle(orm)
    assert engine.volume == 987654.0
    assert isinstance(engine.volume, float)


def test_orm_to_engine_candle__timestamp_passthrough() -> None:
    orm = _make_orm(timestamp=_TS)
    engine = orm_to_engine_candle(orm)
    assert engine.timestamp == _TS


# ═══════════════════════════════════════════════════════════════════════
# engine_candle_to_orm
# ═══════════════════════════════════════════════════════════════════════


def _engine() -> EngineCandle:
    return EngineCandle(
        timestamp=_TS,
        open=1234.56,
        high=1240.00,
        low=1230.00,
        close=1238.75,
        volume=12345.0,
    )


def test_engine_candle_to_orm__float_to_decimal_via_str() -> None:
    eng = EngineCandle(
        timestamp=_TS,
        open=0.1,  # the canonical IEEE-754 footgun
        high=0.2,
        low=0.05,
        close=0.15,
        volume=0.0,
    )
    orm = engine_candle_to_orm(
        eng,
        symbol="X",
        exchange="NSE_EQ",
        timeframe="5m",
        dhan_security_id="1",
    )
    # Decimal(0.1) would be 0.1000000000000000055511151231257827021181583404541015625
    # Decimal(str(0.1)) is exactly 0.1
    assert orm.open == Decimal("0.1")
    assert orm.close == Decimal("0.15")


def test_engine_candle_to_orm__volume_float_truncates_to_int() -> None:
    eng = EngineCandle(
        timestamp=_TS,
        open=100.0,
        high=100.0,
        low=100.0,
        close=100.0,
        volume=99999.0,
    )
    orm = engine_candle_to_orm(
        eng,
        symbol="X",
        exchange="NSE_EQ",
        timeframe="1m",
        dhan_security_id="1",
    )
    assert orm.volume == 99999
    assert isinstance(orm.volume, int)


def test_engine_candle_to_orm__caller_supplies_symbol_exchange_timeframe() -> None:
    orm = engine_candle_to_orm(
        _engine(),
        symbol="TCS",
        exchange="NSE_EQ",
        timeframe="1h",
        dhan_security_id="11536",
    )
    assert orm.symbol == "TCS"
    assert orm.exchange == "NSE_EQ"
    assert orm.timeframe == "1h"
    assert orm.dhan_security_id == "11536"


def test_engine_candle_to_orm__defaults_source_unless_overridden() -> None:
    orm = engine_candle_to_orm(
        _engine(),
        symbol="X",
        exchange="NSE_EQ",
        timeframe="5m",
        dhan_security_id="1",
    )
    assert orm.source == "dhan_v2_historical"
    orm2 = engine_candle_to_orm(
        _engine(),
        symbol="X",
        exchange="NSE_EQ",
        timeframe="5m",
        dhan_security_id="1",
        source="manual_csv_import",
    )
    assert orm2.source == "manual_csv_import"


# ═══════════════════════════════════════════════════════════════════════
# Round-trip property tests
# ═══════════════════════════════════════════════════════════════════════


def test_round_trip__orm_to_chart_to_orm__preserves_decimal() -> None:
    src = _make_orm()
    chart = orm_to_chart_candle(src)
    rebuilt = chart_candle_to_orm(
        chart, exchange=src.exchange, dhan_security_id=src.dhan_security_id
    )
    assert rebuilt.open == src.open
    assert rebuilt.close == src.close
    assert rebuilt.volume == src.volume
    assert rebuilt.symbol == src.symbol
    assert rebuilt.timeframe == src.timeframe


@pytest.mark.parametrize(
    "price_str",
    [
        "42.05",
        "1234.5678",
        "0.0001",
        "9999.9999",
    ],
)
def test_round_trip__orm_to_engine_to_orm__decimal_preserved(price_str: str) -> None:
    """Property: Decimal → float (via str) → Decimal (via str) is identity
    for 4-decimal-place prices, which is the precision the schema mandates.
    """
    price = Decimal(price_str)
    src = _make_orm(open_=price, high=price, low=price, close=price)
    eng = orm_to_engine_candle(src)
    rebuilt = engine_candle_to_orm(
        eng,
        symbol=src.symbol,
        exchange=src.exchange,
        timeframe=src.timeframe,
        dhan_security_id=src.dhan_security_id,
    )
    assert rebuilt.open == price
    assert rebuilt.close == price
