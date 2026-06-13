"""Tests for ``app.services.historical_candles.repository``.

Uses the real local Postgres (docker compose dev DB) via the
``db_session`` rollback fixture — see conftest.py rationale. Each test
operates inside a single transaction that rolls back at teardown, so
even though the dev DB is shared we leave nothing behind.

Coverage targets:
  upsert_batch          — empty no-op, fresh insert, conflict-skip, defaults
  get_window            — inclusive bounds, ASC order, filter isolation, empty
  exists                — true/false paths
  coverage              — empty window, populated window with min/max ts
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.historical_candle import HistoricalCandle
from app.services.historical_candles.repository import (
    CoverageReport,
    HistoricalCandleRepository,
)

_BASE_TS = datetime(2026, 6, 12, 3, 45, tzinfo=UTC)


def _candle(
    *,
    symbol: str,
    exchange: str = "NSE_EQ",
    timeframe: str = "5m",
    timestamp: datetime,
    open_: Decimal = Decimal("100.0000"),
    high: Decimal = Decimal("110.0000"),
    low: Decimal = Decimal("90.0000"),
    close: Decimal = Decimal("105.0000"),
    volume: int = 1000,
    dhan_security_id: str = "999",
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
# upsert_batch
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_upsert_batch__empty_list_is_explicit_noop(
    db_session: AsyncSession,
) -> None:
    repo = HistoricalCandleRepository(db_session)
    inserted = await repo.upsert_batch([])
    assert inserted == 0


@pytest.mark.asyncio
async def test_upsert_batch__fresh_rows_all_inserted(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    candles = [
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS + timedelta(minutes=5 * i))
        for i in range(3)
    ]
    inserted = await repo.upsert_batch(candles)
    assert inserted == 3


@pytest.mark.asyncio
async def test_upsert_batch__duplicate_pk_skips_via_on_conflict(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    first = [_candle(symbol=test_symbol_prefix, timestamp=_BASE_TS)]
    assert await repo.upsert_batch(first) == 1
    # Second call with same PK but different (in-range) close → 0 inserted,
    # no exception. Demonstrates ON CONFLICT DO NOTHING vs. ON CONFLICT DO
    # UPDATE: the existing row is preserved verbatim and the new value
    # discarded silently.
    second = [_candle(symbol=test_symbol_prefix, timestamp=_BASE_TS, close=Decimal("108.0"))]
    assert await repo.upsert_batch(second) == 0


@pytest.mark.asyncio
async def test_upsert_batch__mixed_new_and_duplicate_partial_insert(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    await repo.upsert_batch([_candle(symbol=test_symbol_prefix, timestamp=_BASE_TS)])
    mixed = [
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS),  # dup
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS + timedelta(minutes=5)),
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS + timedelta(minutes=10)),
    ]
    assert await repo.upsert_batch(mixed) == 2


@pytest.mark.asyncio
async def test_upsert_batch__server_defaults_fire_for_omitted_optional_columns(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    """Omitted volume → DB default 0; omitted source → 'dhan_v2_historical';
    omitted fetched_at → now()."""
    repo = HistoricalCandleRepository(db_session)
    raw = HistoricalCandle(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        timestamp=_BASE_TS,
        open=Decimal("100.0000"),
        high=Decimal("110.0000"),
        low=Decimal("90.0000"),
        close=Decimal("105.0000"),
        dhan_security_id="1",
        # volume, source, fetched_at intentionally NOT set
    )
    await repo.upsert_batch([raw])
    stored = await repo.get_window(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS,
    )
    assert len(stored) == 1
    assert stored[0].volume == 0
    assert stored[0].source == "dhan_v2_historical"
    assert stored[0].fetched_at is not None


# ═══════════════════════════════════════════════════════════════════════
# get_window
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_window__inclusive_bounds(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    candles = [
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS + timedelta(minutes=5 * i))
        for i in range(5)
    ]
    await repo.upsert_batch(candles)
    rows = await repo.get_window(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS + timedelta(minutes=20),
    )
    # 0, 5, 10, 15, 20 minutes → all 5 in range
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_get_window__ordered_asc_by_timestamp(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    # Insert deliberately out of order.
    candles = [
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS + timedelta(minutes=10)),
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS),
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS + timedelta(minutes=5)),
    ]
    await repo.upsert_batch(candles)
    rows = await repo.get_window(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS + timedelta(minutes=10),
    )
    timestamps = [r.timestamp for r in rows]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_get_window__other_symbols_filtered_out(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    other = f"{test_symbol_prefix}_OTHER"
    await repo.upsert_batch(
        [
            _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS),
            _candle(symbol=other, timestamp=_BASE_TS),
        ]
    )
    rows = await repo.get_window(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS,
    )
    assert {r.symbol for r in rows} == {test_symbol_prefix}


@pytest.mark.asyncio
async def test_get_window__empty_result_when_no_match(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    rows = await repo.get_window(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS + timedelta(days=1),
    )
    assert rows == []


# ═══════════════════════════════════════════════════════════════════════
# exists
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_exists__true_when_row_present(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    await repo.upsert_batch([_candle(symbol=test_symbol_prefix, timestamp=_BASE_TS)])
    assert (
        await repo.exists(
            symbol=test_symbol_prefix,
            exchange="NSE_EQ",
            timeframe="5m",
            timestamp=_BASE_TS,
        )
        is True
    )


@pytest.mark.asyncio
async def test_exists__false_when_absent(db_session: AsyncSession, test_symbol_prefix: str) -> None:
    repo = HistoricalCandleRepository(db_session)
    assert (
        await repo.exists(
            symbol=test_symbol_prefix,
            exchange="NSE_EQ",
            timeframe="5m",
            timestamp=_BASE_TS,
        )
        is False
    )


@pytest.mark.asyncio
async def test_exists__discriminates_by_timeframe(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    await repo.upsert_batch(
        [_candle(symbol=test_symbol_prefix, timeframe="5m", timestamp=_BASE_TS)]
    )
    assert (
        await repo.exists(
            symbol=test_symbol_prefix,
            exchange="NSE_EQ",
            timeframe="15m",
            timestamp=_BASE_TS,
        )
        is False
    )


# ═══════════════════════════════════════════════════════════════════════
# coverage
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_coverage__empty_window_returns_zero_count_and_none_bounds(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    report = await repo.coverage(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS + timedelta(hours=1),
    )
    assert isinstance(report, CoverageReport)
    assert report.bar_count == 0
    assert report.first_bar_ts is None
    assert report.last_bar_ts is None


@pytest.mark.asyncio
async def test_coverage__counts_and_min_max_timestamps_populated(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    candles = [
        _candle(symbol=test_symbol_prefix, timestamp=_BASE_TS + timedelta(minutes=5 * i))
        for i in range(4)
    ]
    await repo.upsert_batch(candles)
    report = await repo.coverage(
        symbol=test_symbol_prefix,
        exchange="NSE_EQ",
        timeframe="5m",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS + timedelta(hours=1),
    )
    assert report.bar_count == 4
    assert report.first_bar_ts == _BASE_TS
    assert report.last_bar_ts == _BASE_TS + timedelta(minutes=15)


@pytest.mark.asyncio
async def test_coverage__echoes_query_parameters(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalCandleRepository(db_session)
    report = await repo.coverage(
        symbol=test_symbol_prefix,
        exchange="BSE_EQ",
        timeframe="1h",
        from_ts=_BASE_TS,
        to_ts=_BASE_TS + timedelta(days=1),
    )
    assert report.symbol == test_symbol_prefix
    assert report.exchange == "BSE_EQ"
    assert report.timeframe == "1h"
    assert report.from_ts == _BASE_TS
    assert report.to_ts == _BASE_TS + timedelta(days=1)
