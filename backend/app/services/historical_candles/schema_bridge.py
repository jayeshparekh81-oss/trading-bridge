"""Pure bridge between the three OHLC shapes that share this store.

The historical_candles ORM (``app.db.models.historical_candle``) is the
canonical persistent shape — Decimal(18, 4) prices, BigInteger volume,
``symbol/exchange/timeframe/timestamp`` composite identity.

Two other Candle shapes flow in and out:

1. **Chart Candle** — ``app.schemas.candle.Candle`` — Pydantic v2 strict,
   Decimal prices, ``Timeframe`` enum. Used by the live chart WS, the
   REST history endpoint, and any HTTP boundary that returns OHLC to a
   browser or API client.

2. **Engine Candle** — ``app.strategy_engine.schema.ohlcv.Candle`` —
   Pydantic v2, **float** prices and volume, no symbol or timeframe
   (those live one layer up in the engine's invocation context). Used
   by the backtest engine hot loop and TA-Lib indicator inputs, where
   per-bar Decimal overhead would be wasteful.

The four functions below are **pure** — no I/O, no logging, no DB
sessions. Decimal↔float conversion routes through ``str()`` so that
paise-precision round-trips losslessly (``float(Decimal('42.05'))``
returns ``42.05`` but ``Decimal(42.05)`` gives ``42.0499...``;
``Decimal(str(42.05))`` gives the exact ``Decimal('42.05')``). This
single discipline is what keeps Q3 P&L reconciliations honest.

Callers MUST pre-filter inputs: the ORM enforces a 5-value
``ck_hc_timeframe_enum`` (``1m, 5m, 15m, 1h, 1d``) but the chart
Timeframe enum is wider (``3m, 30m`` also exist). Passing an
unsupported timeframe will be caught by the DB CHECK on flush, not
here — by design, the bridge stays free of policy. Phase 3 orchestrator
owns the upstream filter.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.db.models.historical_candle import HistoricalCandle
from app.schemas.candle import Candle as ChartCandle
from app.schemas.candle import Timeframe
from app.strategy_engine.schema.ohlcv import Candle as EngineCandle

_DEFAULT_SOURCE = "dhan_v2_historical"


def orm_to_chart_candle(orm: HistoricalCandle) -> ChartCandle:
    """ORM row → strict Pydantic chart Candle (Decimal preserved verbatim).

    Used by the REST history endpoint and the chart-history Redis cache
    serialiser; both want the Decimal-strict shape so the JSON wire
    format keeps OHLC as numeric strings rather than float literals.
    """
    return ChartCandle(
        symbol=orm.symbol,
        timeframe=Timeframe(orm.timeframe),
        timestamp=orm.timestamp,
        open=orm.open,
        high=orm.high,
        low=orm.low,
        close=orm.close,
        volume=orm.volume,
    )


def chart_candle_to_orm(
    candle: ChartCandle,
    *,
    exchange: str,
    dhan_security_id: str,
    fetched_by_user_id: uuid.UUID | None = None,
    source: str = _DEFAULT_SOURCE,
) -> HistoricalCandle:
    """Strict chart Candle → ORM row (Decimal preserved verbatim).

    The chart Candle carries ``symbol`` and ``timeframe`` but not
    ``exchange`` / ``dhan_security_id`` / provenance — those are
    supplied by the caller (typically the Phase 3 orchestrator or a
    historical-fetch task). Keyword-only to keep call-sites readable
    when the orchestrator stamps multiple bars in a loop.
    """
    return HistoricalCandle(
        symbol=candle.symbol,
        exchange=exchange,
        timeframe=candle.timeframe.value,
        timestamp=candle.timestamp,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        dhan_security_id=dhan_security_id,
        source=source,
        fetched_by_user_id=fetched_by_user_id,
    )


def orm_to_engine_candle(orm: HistoricalCandle) -> EngineCandle:
    """ORM row → backtest-engine OHLCV Candle (Decimal → float via str()).

    The engine works in float for speed; the bridge crosses precision
    domains here. ``float(str(decimal))`` keeps the decimal text exact
    on the way to the IEEE-754 representation, so a price stored as
    ``Decimal('1234.5600')`` arrives at the engine as ``1234.56``
    rather than ``1234.5599999...``.
    """
    return EngineCandle(
        timestamp=orm.timestamp,
        open=float(str(orm.open)),
        high=float(str(orm.high)),
        low=float(str(orm.low)),
        close=float(str(orm.close)),
        volume=float(orm.volume),
    )


def engine_candle_to_orm(
    candle: EngineCandle,
    *,
    symbol: str,
    exchange: str,
    timeframe: str,
    dhan_security_id: str,
    fetched_by_user_id: uuid.UUID | None = None,
    source: str = _DEFAULT_SOURCE,
) -> HistoricalCandle:
    """Backtest-engine OHLCV Candle → ORM row (float → Decimal via str()).

    Used when engine output is being persisted back (e.g. resampled
    timeframes computed in Phase 3+). ``Decimal(str(float_price))`` is
    the only safe path: ``Decimal(0.1)`` is ``Decimal('0.10000000...')``
    whereas ``Decimal(str(0.1))`` is the exact ``Decimal('0.1')``.

    Engine volume is float for hot-loop ergonomics; we truncate back to
    int for the BigInteger column — engine volumes are always
    whole-share counts so the truncation is information-preserving in
    every legitimate code path.
    """
    return HistoricalCandle(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        timestamp=candle.timestamp,
        open=Decimal(str(candle.open)),
        high=Decimal(str(candle.high)),
        low=Decimal(str(candle.low)),
        close=Decimal(str(candle.close)),
        volume=int(candle.volume),
        dhan_security_id=dhan_security_id,
        source=source,
        fetched_by_user_id=fetched_by_user_id,
    )


__all__ = [
    "chart_candle_to_orm",
    "engine_candle_to_orm",
    "orm_to_chart_candle",
    "orm_to_engine_candle",
]
