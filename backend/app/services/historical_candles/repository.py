"""Async repository for ``historical_candles`` persistence.

Owns four read/write entry points:

* :meth:`HistoricalCandleRepository.upsert_batch` — idempotent batch
  insert using PostgreSQL's ``INSERT … ON CONFLICT DO NOTHING`` keyed
  on the composite PK ``(symbol, exchange, timeframe, timestamp)``.
  Returns the actually-inserted row count (skipped = submitted -
  inserted). Re-fetching the same Dhan window twice is therefore a
  free no-op at the DB layer.
* :meth:`HistoricalCandleRepository.get_window` — bars in
  ``[from_ts, to_ts]`` inclusive for a single
  ``(symbol, exchange, timeframe)`` tuple, ordered ASC by timestamp.
* :meth:`HistoricalCandleRepository.exists` — single-bar existence
  probe; quick pre-flight for "is this slot already filled".
* :meth:`HistoricalCandleRepository.coverage` —
  :class:`CoverageReport` summarising bar_count + first/last
  timestamp over the window. Phase 3 backtest orchestrator will use
  it to decide whether to backfill before kicking off a run.

Logging discipline: one structured JSON log per upsert call (NOT per
candle inside the loop) carrying submitted/inserted/skipped counts +
a one-bar sample (symbol, timeframe) for human grep. Reads stay
silent on happy path; callers may add user_id / request_id context
at the orchestrator layer where it is naturally available.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.historical_candle import HistoricalCandle

logger = logging.getLogger(__name__)


_REQUIRED_COLUMNS: tuple[str, ...] = (
    "symbol",
    "exchange",
    "timeframe",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "dhan_security_id",
)
_DEFAULTED_COLUMNS: tuple[str, ...] = (
    "volume",
    "source",
    "fetched_at",
    "fetched_by_user_id",
    "quality_score",
)


class CoverageReport(BaseModel):
    """Summary of how densely a (symbol, exchange, timeframe, window)
    slice is populated in ``historical_candles``.

    The skeleton intentionally returns raw bar_count rather than a
    percentage — computing "expected_bars" honestly requires the NSE /
    BSE session calendar (intraday timeframes only count market
    minutes), which is a Phase 3+ concern. Callers that need a quick
    sanity check can divide by their own expected-bar heuristic.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    exchange: str
    timeframe: str
    from_ts: datetime
    to_ts: datetime
    bar_count: int = Field(ge=0)
    first_bar_ts: datetime | None
    last_bar_ts: datetime | None


class HistoricalCandleRepository:
    """Thin async wrapper around the ``historical_candles`` table.

    Stateless beyond the session reference; safe to construct per
    request. Phase 3 orchestrator / Celery tasks will instantiate
    one per DB session, do their work, and let it fall out of scope.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_batch(self, candles: list[HistoricalCandle]) -> int:
        """Idempotent batch insert. Returns count of NEW rows inserted.

        ``ON CONFLICT (pk_historical_candles) DO NOTHING`` makes this
        safe to call with overlapping windows — re-fetching yesterday's
        and today's bars together will only insert the truly new ones.
        Empty input is an explicit no-op (no SQL emitted, no log).
        """
        if not candles:
            return 0

        rows = [self._orm_to_row(c) for c in candles]

        stmt = (
            pg_insert(HistoricalCandle)
            .values(rows)
            .on_conflict_do_nothing(
                constraint="pk_historical_candles",
            )
        )
        result = await self._session.execute(stmt)
        inserted = result.rowcount or 0
        skipped = len(candles) - inserted

        logger.info(
            json.dumps(
                {
                    "event": "historical_candles.upsert_batch",
                    "submitted": len(candles),
                    "inserted": inserted,
                    "skipped": skipped,
                    "symbol_sample": candles[0].symbol,
                    "exchange_sample": candles[0].exchange,
                    "timeframe_sample": candles[0].timeframe,
                }
            )
        )
        return inserted

    async def get_window(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> list[HistoricalCandle]:
        """Bars in ``[from_ts, to_ts]`` inclusive, ordered ASC.

        Hits ``idx_hc_lookup`` for the predicate; the index is built
        DESC on timestamp so PG reads it backwards for ASC ordering —
        still index-only, no Sort node. Returns an empty list when no
        bars match (caller decides whether to backfill).
        """
        stmt = (
            select(HistoricalCandle)
            .where(
                HistoricalCandle.symbol == symbol,
                HistoricalCandle.exchange == exchange,
                HistoricalCandle.timeframe == timeframe,
                HistoricalCandle.timestamp >= from_ts,
                HistoricalCandle.timestamp <= to_ts,
            )
            .order_by(HistoricalCandle.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def exists(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        timestamp: datetime,
    ) -> bool:
        """True iff a bar with the exact composite key is stored.

        Used by the Phase 3 orchestrator to decide whether to call
        Dhan at all for a single timestamp (e.g. a late-arriving
        in-progress bar that has since closed).
        """
        stmt = (
            select(func.count())
            .select_from(HistoricalCandle)
            .where(
                HistoricalCandle.symbol == symbol,
                HistoricalCandle.exchange == exchange,
                HistoricalCandle.timeframe == timeframe,
                HistoricalCandle.timestamp == timestamp,
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def coverage(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> CoverageReport:
        """Coverage summary for a (symbol, exchange, timeframe, window).

        Single aggregate query — one round-trip — returns row count
        and the actual first/last stored timestamps inside the window.
        Phase 3 backtest pre-flight will compare against an
        expected-bar count derived from the trading calendar to flag
        gaps before a run launches.
        """
        stmt = (
            select(
                func.count().label("bar_count"),
                func.min(HistoricalCandle.timestamp).label("first_bar_ts"),
                func.max(HistoricalCandle.timestamp).label("last_bar_ts"),
            )
            .select_from(HistoricalCandle)
            .where(
                HistoricalCandle.symbol == symbol,
                HistoricalCandle.exchange == exchange,
                HistoricalCandle.timeframe == timeframe,
                HistoricalCandle.timestamp >= from_ts,
                HistoricalCandle.timestamp <= to_ts,
            )
        )
        result = await self._session.execute(stmt)
        row = result.one()
        return CoverageReport(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            from_ts=from_ts,
            to_ts=to_ts,
            bar_count=row.bar_count,
            first_bar_ts=row.first_bar_ts,
            last_bar_ts=row.last_bar_ts,
        )

    @staticmethod
    def _orm_to_row(candle: HistoricalCandle) -> dict[str, object]:
        """Project a transient HistoricalCandle into a dict suitable for
        ``pg_insert(...).values([...])``.

        Optional columns with server-side defaults (``volume``,
        ``source``, ``fetched_at``, …) are OMITTED when the ORM value
        is ``None`` so the DB-level default fires. Required columns are
        always emitted; an upsert with a missing required value will
        fail at the DB boundary, which is the safer outcome (silent
        partial inserts would be worse).
        """
        row: dict[str, object] = {col: getattr(candle, col) for col in _REQUIRED_COLUMNS}
        for col in _DEFAULTED_COLUMNS:
            value = getattr(candle, col, None)
            if value is not None:
                row[col] = value
        return row


__all__ = ["CoverageReport", "HistoricalCandleRepository"]
