"""Tests for ``app.services.historical_candles.orchestrator``.

Strategy: mock both ``DhanHistoricalClient`` and the repository.
The orchestrator's role is pure coordination — chunk, call, convert,
persist — so unit-level mocking covers it 1:1.

Test matrix:
    * chunk_window: single-chunk, 90-day boundary, multi-chunk intraday,
      multi-chunk daily, inverted window raises
    * compute_quality_score: 0 expected, 0 actual, partial, full, over-count
    * _expected_calendar_bars: zero window, normal, sub-step
    * HistoricalCandleOrchestrator.fetch_and_persist:
        - single chunk, all bars insert
        - multi-chunk window, cumulative counts
        - empty Dhan response, quality=0
        - Dhan exception propagates + client.aclose() still called
        - quality_score stamped on each ORM row
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.candle import Candle as ChartCandle
from app.schemas.candle import Timeframe
from app.services.historical_candles.orchestrator import (
    HistoricalCandleOrchestrator,
    OrchestratorReport,
    _expected_calendar_bars,
    chunk_window,
    compute_quality_score,
)


# ═══════════════════════════════════════════════════════════════════════
# chunk_window
# ═══════════════════════════════════════════════════════════════════════


def test_chunk_window__single_chunk_when_within_limit() -> None:
    f = datetime(2026, 6, 1, tzinfo=UTC)
    t = datetime(2026, 6, 30, tzinfo=UTC)
    chunks = chunk_window(from_ts=f, to_ts=t, timeframe=Timeframe.FIVE_MIN)
    assert chunks == [(f, t)]


def test_chunk_window__exactly_90_days_intraday_single_chunk() -> None:
    f = datetime(2026, 3, 1, tzinfo=UTC)
    t = f + timedelta(days=90)
    chunks = chunk_window(from_ts=f, to_ts=t, timeframe=Timeframe.ONE_MIN)
    assert len(chunks) == 1
    assert chunks[0] == (f, t)


def test_chunk_window__91_days_intraday_splits_into_two() -> None:
    f = datetime(2026, 3, 1, tzinfo=UTC)
    t = f + timedelta(days=91)
    chunks = chunk_window(from_ts=f, to_ts=t, timeframe=Timeframe.ONE_HOUR)
    assert len(chunks) == 2
    # First chunk: 90 days
    assert chunks[0][1] == f + timedelta(days=90)
    # Second chunk starts 1 second later, ends at to_ts
    assert chunks[1][0] == f + timedelta(days=90, seconds=1)
    assert chunks[1][1] == t


def test_chunk_window__daily_uses_5_year_chunks() -> None:
    f = datetime(2020, 1, 1, tzinfo=UTC)
    t = datetime(2026, 6, 1, tzinfo=UTC)  # >5 years
    chunks = chunk_window(from_ts=f, to_ts=t, timeframe=Timeframe.ONE_DAY)
    assert len(chunks) == 2  # 5 years + the remainder


def test_chunk_window__daily_within_5_years_single_chunk() -> None:
    f = datetime(2022, 1, 1, tzinfo=UTC)
    t = datetime(2026, 6, 1, tzinfo=UTC)
    chunks = chunk_window(from_ts=f, to_ts=t, timeframe=Timeframe.ONE_DAY)
    assert chunks == [(f, t)]


def test_chunk_window__from_after_to_raises() -> None:
    with pytest.raises(ValueError, match=">"):
        chunk_window(
            from_ts=datetime(2026, 6, 30, tzinfo=UTC),
            to_ts=datetime(2026, 6, 1, tzinfo=UTC),
            timeframe=Timeframe.ONE_DAY,
        )


# ═══════════════════════════════════════════════════════════════════════
# compute_quality_score
# ═══════════════════════════════════════════════════════════════════════


def test_quality__zero_expected_returns_zero() -> None:
    assert compute_quality_score(actual_bars=5, expected_bars=0) == Decimal("0.00")


def test_quality__zero_actual_returns_zero() -> None:
    assert compute_quality_score(actual_bars=0, expected_bars=100) == Decimal("0.00")


def test_quality__partial_returns_ratio() -> None:
    score = compute_quality_score(actual_bars=50, expected_bars=100)
    assert score == Decimal("0.50")


def test_quality__full_returns_one() -> None:
    assert compute_quality_score(actual_bars=100, expected_bars=100) == Decimal("1.00")


def test_quality__overcount_caps_at_one() -> None:
    assert compute_quality_score(actual_bars=150, expected_bars=100) == Decimal("1.00")


def test_quality__quantises_to_two_decimals() -> None:
    score = compute_quality_score(actual_bars=1, expected_bars=3)
    # 1/3 = 0.333... → 0.33
    assert score == Decimal("0.33")


# ═══════════════════════════════════════════════════════════════════════
# _expected_calendar_bars
# ═══════════════════════════════════════════════════════════════════════


def test_expected_bars__zero_window_returns_zero() -> None:
    ts = datetime(2026, 6, 1, tzinfo=UTC)
    assert _expected_calendar_bars(ts, ts, Timeframe.ONE_MIN) == 0


def test_expected_bars__one_hour_window_5min_timeframe_returns_12() -> None:
    f = datetime(2026, 6, 1, tzinfo=UTC)
    t = f + timedelta(hours=1)
    assert _expected_calendar_bars(f, t, Timeframe.FIVE_MIN) == 12


def test_expected_bars__sub_step_window_returns_one() -> None:
    f = datetime(2026, 6, 1, tzinfo=UTC)
    t = f + timedelta(seconds=30)
    # Less than one 1m bar → floors to 0 → floored up to 1 (min bar count).
    assert _expected_calendar_bars(f, t, Timeframe.ONE_MIN) == 1


# ═══════════════════════════════════════════════════════════════════════
# HistoricalCandleOrchestrator.fetch_and_persist
# ═══════════════════════════════════════════════════════════════════════


def _make_chart_candle(
    *, symbol: str = "RELIANCE", offset_minutes: int = 0
) -> ChartCandle:
    ts = datetime(2026, 6, 1, 9, 15, tzinfo=UTC) + timedelta(
        minutes=offset_minutes
    )
    return ChartCandle(
        symbol=symbol,
        timeframe=Timeframe.FIVE_MIN,
        timestamp=ts,
        open=Decimal("100.00"),
        high=Decimal("110.00"),
        low=Decimal("90.00"),
        close=Decimal("105.00"),
        volume=1000,
    )


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.upsert_batch = AsyncMock(return_value=0)  # default; tests override
    return repo


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.get_historical_ohlc = AsyncMock(return_value=[])
    client.aclose = AsyncMock(return_value=None)
    return client


@pytest.fixture
def factory_returning(mock_client: MagicMock):
    async def factory() -> MagicMock:
        return mock_client

    return factory


async def test_fetch_and_persist__single_chunk_happy_path(
    mock_repo: MagicMock,
    mock_client: MagicMock,
    factory_returning,
) -> None:
    bars = [_make_chart_candle(offset_minutes=5 * i) for i in range(3)]
    mock_client.get_historical_ohlc.return_value = bars
    mock_repo.upsert_batch.return_value = 3

    orch = HistoricalCandleOrchestrator(
        repository=mock_repo, client_factory=factory_returning
    )
    report = await orch.fetch_and_persist(
        symbol="RELIANCE",
        exchange="NSE_EQ",
        security_id="2885",
        instrument="EQUITY",
        timeframe=Timeframe.FIVE_MIN,
        from_ts=datetime(2026, 6, 1, tzinfo=UTC),
        to_ts=datetime(2026, 6, 2, tzinfo=UTC),
    )

    assert isinstance(report, OrchestratorReport)
    assert report.chunks_requested == 1
    assert report.bars_fetched == 3
    assert report.bars_inserted == 3
    assert mock_client.get_historical_ohlc.await_count == 1
    assert mock_repo.upsert_batch.await_count == 1
    mock_client.aclose.assert_awaited()


async def test_fetch_and_persist__multi_chunk_aggregates_counts(
    mock_repo: MagicMock,
    mock_client: MagicMock,
    factory_returning,
) -> None:
    # 100-day intraday window → 2 chunks.
    bars_per_chunk = [_make_chart_candle(offset_minutes=5 * i) for i in range(4)]
    mock_client.get_historical_ohlc.return_value = bars_per_chunk
    mock_repo.upsert_batch.return_value = 4

    orch = HistoricalCandleOrchestrator(
        repository=mock_repo, client_factory=factory_returning
    )
    report = await orch.fetch_and_persist(
        symbol="RELIANCE",
        exchange="NSE_EQ",
        security_id="2885",
        instrument="EQUITY",
        timeframe=Timeframe.FIFTEEN_MIN,
        from_ts=datetime(2026, 3, 1, tzinfo=UTC),
        to_ts=datetime(2026, 3, 1, tzinfo=UTC) + timedelta(days=100),
    )

    assert report.chunks_requested == 2
    assert report.bars_fetched == 8  # 4 per chunk × 2 chunks
    assert report.bars_inserted == 8
    assert mock_client.get_historical_ohlc.await_count == 2
    assert mock_repo.upsert_batch.await_count == 2


async def test_fetch_and_persist__empty_response_yields_quality_zero(
    mock_repo: MagicMock,
    mock_client: MagicMock,
    factory_returning,
) -> None:
    mock_client.get_historical_ohlc.return_value = []
    mock_repo.upsert_batch.return_value = 0

    orch = HistoricalCandleOrchestrator(
        repository=mock_repo, client_factory=factory_returning
    )
    report = await orch.fetch_and_persist(
        symbol="X",
        exchange="NSE_EQ",
        security_id="1",
        instrument="EQUITY",
        timeframe=Timeframe.ONE_HOUR,
        from_ts=datetime(2026, 6, 1, tzinfo=UTC),
        to_ts=datetime(2026, 6, 2, tzinfo=UTC),
    )
    assert report.bars_fetched == 0
    assert report.bars_inserted == 0
    assert report.quality_score_avg == Decimal("0.00")
    # Empty list still results in an upsert_batch([]) call → 0 inserted, no SQL.
    assert mock_repo.upsert_batch.await_count == 1


async def test_fetch_and_persist__dhan_exception_propagates_and_closes_client(
    mock_repo: MagicMock,
    mock_client: MagicMock,
    factory_returning,
) -> None:
    class _SimulatedBrokerError(RuntimeError):
        pass

    mock_client.get_historical_ohlc.side_effect = _SimulatedBrokerError("429")

    orch = HistoricalCandleOrchestrator(
        repository=mock_repo, client_factory=factory_returning
    )
    with pytest.raises(_SimulatedBrokerError):
        await orch.fetch_and_persist(
            symbol="X",
            exchange="NSE_EQ",
            security_id="1",
            instrument="EQUITY",
            timeframe=Timeframe.ONE_MIN,
            from_ts=datetime(2026, 6, 1, tzinfo=UTC),
            to_ts=datetime(2026, 6, 2, tzinfo=UTC),
        )
    mock_client.aclose.assert_awaited()  # finally clause ran


async def test_fetch_and_persist__quality_score_stamped_on_each_orm_row(
    mock_repo: MagicMock,
    mock_client: MagicMock,
    factory_returning,
) -> None:
    bars = [_make_chart_candle(offset_minutes=5 * i) for i in range(2)]
    mock_client.get_historical_ohlc.return_value = bars
    mock_repo.upsert_batch.return_value = 2

    orch = HistoricalCandleOrchestrator(
        repository=mock_repo, client_factory=factory_returning
    )
    await orch.fetch_and_persist(
        symbol="RELIANCE",
        exchange="NSE_EQ",
        security_id="2885",
        instrument="EQUITY",
        timeframe=Timeframe.FIVE_MIN,
        from_ts=datetime(2026, 6, 1, tzinfo=UTC),
        to_ts=datetime(2026, 6, 1, 0, 30, tzinfo=UTC),
    )
    # First call argument list — list of ORM rows passed to upsert_batch.
    orm_rows = mock_repo.upsert_batch.call_args.args[0]
    assert len(orm_rows) == 2
    for row in orm_rows:
        assert row.quality_score is not None
        assert isinstance(row.quality_score, Decimal)


async def test_fetch_and_persist__provenance_fields_propagate(
    mock_repo: MagicMock,
    mock_client: MagicMock,
    factory_returning,
) -> None:
    bars = [_make_chart_candle()]
    mock_client.get_historical_ohlc.return_value = bars
    mock_repo.upsert_batch.return_value = 1

    user = uuid.uuid4()
    orch = HistoricalCandleOrchestrator(
        repository=mock_repo, client_factory=factory_returning
    )
    await orch.fetch_and_persist(
        symbol="RELIANCE",
        exchange="NSE_EQ",
        security_id="2885",
        instrument="EQUITY",
        timeframe=Timeframe.FIVE_MIN,
        from_ts=datetime(2026, 6, 1, tzinfo=UTC),
        to_ts=datetime(2026, 6, 1, 0, 30, tzinfo=UTC),
        fetched_by_user_id=user,
    )
    orm_rows = mock_repo.upsert_batch.call_args.args[0]
    assert orm_rows[0].exchange == "NSE_EQ"
    assert orm_rows[0].dhan_security_id == "2885"
    assert orm_rows[0].fetched_by_user_id == user
