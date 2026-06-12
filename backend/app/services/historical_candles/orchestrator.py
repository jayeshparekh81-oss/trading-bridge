"""Phase 3 orchestrator — Dhan historical fetch → bridge → repo persist.

End-to-end coordinator for a single (symbol, exchange, timeframe, window)
backfill operation:

    1. **Chunk the window** per Dhan v2 limits — ≤90 days for intraday,
       ≤5 years for daily. Larger requests would be rejected.
    2. **Fetch via** :class:`~app.brokers.dhan_historical.DhanHistoricalClient`
       — passed in by the caller so tests can inject a mock. Module
       imports :class:`Candle` and :class:`Timeframe` from the chart
       schemas (read-only).
    3. **Bridge** each chart Candle into an ORM
       :class:`~app.db.models.historical_candle.HistoricalCandle`
       via :func:`schema_bridge.chart_candle_to_orm`, stamping
       ``quality_score`` per the chunk-level calculation below.
    4. **Persist** through
       :meth:`HistoricalCandleRepository.upsert_batch` so re-fetching
       the same window is a free no-op via ``ON CONFLICT DO NOTHING``.

The orchestrator does NOT own the transaction boundary. The caller —
typically the Celery backfill task — wraps the call in its own
session/commit. This keeps the orchestrator pure(-ish) and easy to
unit-test with a mocked-out repo.

Quality-score (Q6A): a skeleton calculation that compares received
bars to the calendar-bar expectation. **Treats the window as
continuous 24x7**, so intraday timeframes will under-report quality
(market hours are a fraction of the calendar day). Phase 3+ will
plug in an NSE/BSE session calendar; for now we floor at 0 and cap
at 1.0, store as ``Decimal('x.xx')``. Empty responses get 0.00.

The orchestrator imports nothing from this project that isn't already
deployed — :class:`DhanHistoricalClient`, :class:`HistoricalCandle`,
:class:`HistoricalCandleRepository`, :mod:`schema_bridge`,
:class:`Timeframe`. No edits to those files; this is additive Phase 3
code only.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.brokers.dhan_historical import DhanHistoricalClient
from app.schemas.candle import Candle as ChartCandle
from app.schemas.candle import Timeframe
from app.services.historical_candles.repository import (
    HistoricalCandleRepository,
)
from app.services.historical_candles.schema_bridge import chart_candle_to_orm

logger = logging.getLogger(__name__)

# Dhan v2 historical chunk caps (documented in dhan_historical.py header).
_INTRADAY_MAX_DAYS = 90
_DAILY_MAX_DAYS = 365 * 5  # 5 years (calendar — leap-year imprecision tolerated)

_INTRADAY_TIMEFRAMES: frozenset[Timeframe] = frozenset(
    {
        Timeframe.ONE_MIN,
        Timeframe.FIVE_MIN,
        Timeframe.FIFTEEN_MIN,
        Timeframe.ONE_HOUR,
    }
)


@dataclass(frozen=True)
class OrchestratorReport:
    """Summary of one ``fetch_and_persist`` invocation."""

    chunks_requested: int
    bars_fetched: int
    bars_inserted: int  # net inserts post-ON CONFLICT (skipped = fetched - inserted)
    quality_score_avg: Decimal  # mean across non-empty chunks


# Type alias for a function that yields a DhanHistoricalClient context
# manager. The orchestrator never instantiates the client directly so
# tests can pass an AsyncMock without touching the network.
DhanClientFactory = Callable[
    [], "AsyncIterator[DhanHistoricalClient]"
]


def chunk_window(
    *,
    from_ts: datetime,
    to_ts: datetime,
    timeframe: Timeframe,
) -> list[tuple[datetime, datetime]]:
    """Break ``[from_ts, to_ts]`` into Dhan-compliant chunks.

    Intraday (1m/5m/15m/1h) → 90-day chunks max. Daily → 5-year chunks
    max. The last chunk's end is clamped to ``to_ts``; never extends
    past the requested window.

    Single-chunk windows are returned as a one-element list.
    """
    if from_ts > to_ts:
        raise ValueError(
            f"from_ts ({from_ts.isoformat()}) > to_ts ({to_ts.isoformat()})."
        )

    max_days = (
        _INTRADAY_MAX_DAYS
        if timeframe in _INTRADAY_TIMEFRAMES
        else _DAILY_MAX_DAYS
    )
    max_delta = timedelta(days=max_days)

    chunks: list[tuple[datetime, datetime]] = []
    chunk_start = from_ts
    while chunk_start <= to_ts:
        chunk_end = min(chunk_start + max_delta, to_ts)
        chunks.append((chunk_start, chunk_end))
        if chunk_end >= to_ts:
            break
        chunk_start = chunk_end + timedelta(seconds=1)
    return chunks


def compute_quality_score(
    *, actual_bars: int, expected_bars: int
) -> Decimal:
    """Cap-and-round quality metric: ``min(actual/expected, 1.0)``.

    Returns ``Decimal('0.00')`` for empty responses or non-positive
    ``expected_bars``. Capped at ``Decimal('1.00')`` so the column's
    ``Numeric(5, 2)`` precision can never overflow on the upside even
    if a future Dhan response over-counts.
    """
    if expected_bars <= 0 or actual_bars <= 0:
        return Decimal("0.00")
    ratio = Decimal(actual_bars) / Decimal(expected_bars)
    capped = min(ratio, Decimal("1"))
    return capped.quantize(Decimal("0.01"))


def _expected_calendar_bars(
    from_ts: datetime, to_ts: datetime, timeframe: Timeframe
) -> int:
    """Naive expected bar count assuming continuous 24x7 trading.

    Acknowledged inaccuracy for intraday timeframes; Phase 3+ swaps in
    a session calendar. The skeleton keeps the maths obvious so reviewers
    can see exactly what the quality_score is normalising against.
    """
    seconds = (to_ts - from_ts).total_seconds()
    if seconds <= 0:
        return 0
    return max(1, int(seconds // timeframe.seconds))


class HistoricalCandleOrchestrator:
    """Drives one symbol/timeframe window from Dhan to the
    ``historical_candles`` store."""

    def __init__(
        self,
        *,
        repository: HistoricalCandleRepository,
        client_factory: Callable[
            [], Awaitable[DhanHistoricalClient]
        ],
    ) -> None:
        """
        Args:
            repository: Caller-supplied
                :class:`HistoricalCandleRepository` bound to the
                caller's AsyncSession. The orchestrator never opens
                a session.
            client_factory: Async callable returning a ready-to-use
                :class:`DhanHistoricalClient`. The orchestrator calls
                this once per ``fetch_and_persist`` invocation and
                reuses the returned client across all chunks. Tests
                pass an ``AsyncMock`` here.
        """
        self._repository = repository
        self._client_factory = client_factory

    async def fetch_and_persist(
        self,
        *,
        symbol: str,
        exchange: str,
        security_id: str,
        instrument: str,
        timeframe: Timeframe,
        from_ts: datetime,
        to_ts: datetime,
        fetched_by_user_id: uuid.UUID | None = None,
    ) -> OrchestratorReport:
        """Run the full chunk/fetch/bridge/persist sweep.

        Returns an :class:`OrchestratorReport` with cumulative counts.
        Logs one structured INFO line at the end. Exceptions from the
        Dhan client or the repository propagate unchanged — the
        caller's Celery task layer is responsible for catching them
        and translating into ``jobs_repository.mark_failed`` payloads.
        """
        chunks = chunk_window(
            from_ts=from_ts, to_ts=to_ts, timeframe=timeframe
        )

        client = await self._client_factory()
        try:
            total_fetched = 0
            total_inserted = 0
            chunk_qualities: list[Decimal] = []

            for chunk_from, chunk_to in chunks:
                candles: list[ChartCandle] = await client.get_historical_ohlc(
                    symbol=symbol,
                    security_id=security_id,
                    exchange_segment=exchange,
                    instrument=instrument,
                    timeframe=timeframe,
                    from_ts=chunk_from,
                    to_ts=chunk_to,
                )

                expected = _expected_calendar_bars(
                    chunk_from, chunk_to, timeframe
                )
                quality = compute_quality_score(
                    actual_bars=len(candles), expected_bars=expected
                )
                if candles:
                    chunk_qualities.append(quality)

                orm_rows = [
                    self._bridge_with_quality(
                        c,
                        exchange=exchange,
                        dhan_security_id=security_id,
                        fetched_by_user_id=fetched_by_user_id,
                        quality_score=quality,
                    )
                    for c in candles
                ]

                inserted = await self._repository.upsert_batch(orm_rows)
                total_fetched += len(candles)
                total_inserted += inserted
        finally:
            await client.aclose()

        avg_quality = (
            sum(chunk_qualities, Decimal("0")) / Decimal(len(chunk_qualities))
            if chunk_qualities
            else Decimal("0.00")
        )
        # Quantise the avg to 2dp so logs / report shapes are stable.
        avg_quality = avg_quality.quantize(Decimal("0.01"))

        report = OrchestratorReport(
            chunks_requested=len(chunks),
            bars_fetched=total_fetched,
            bars_inserted=total_inserted,
            quality_score_avg=avg_quality,
        )

        import json as _json
        logger.info(
            _json.dumps(
                {
                    "event": "historical_candles.orchestrator.fetch_and_persist",
                    "symbol": symbol,
                    "exchange": exchange,
                    "timeframe": timeframe.value,
                    "chunks": report.chunks_requested,
                    "bars_fetched": report.bars_fetched,
                    "bars_inserted": report.bars_inserted,
                    "quality_avg": str(report.quality_score_avg),
                }
            )
        )
        return report

    @staticmethod
    def _bridge_with_quality(
        chart_candle: ChartCandle,
        *,
        exchange: str,
        dhan_security_id: str,
        fetched_by_user_id: uuid.UUID | None,
        quality_score: Decimal,
    ):
        """Run ``chart_candle_to_orm`` and stamp quality_score after.

        The bridge function intentionally doesn't know about
        quality_score (it's a Phase 3 concern, not a per-bar shape
        concern). Setting it here keeps the bridge pure.
        """
        orm = chart_candle_to_orm(
            chart_candle,
            exchange=exchange,
            dhan_security_id=dhan_security_id,
            fetched_by_user_id=fetched_by_user_id,
        )
        orm.quality_score = quality_score
        return orm


__all__ = [
    "HistoricalCandleOrchestrator",
    "OrchestratorReport",
    "chunk_window",
    "compute_quality_score",
]
