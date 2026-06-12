"""Tests for ``app.services.historical_candles.jobs_repository``.

ALL tests in this module SKIP at collection time because migration 030
``030_historical_backfill_jobs`` is **file-only** as of the overnight
session 2026-06-12 — the founder applies it under a morning gate (see
``docs/QUEUE_CCC_OVERNIGHT_BRIEF.md`` parked-gate (a)). Until then the
``historical_backfill_jobs`` table does not exist in the dev DB and
any repo call would fail with ``UndefinedTableError``.

When the founder applies 030, removing the module-level ``pytestmark``
is the only edit needed to enable the suite — the test bodies are
intentionally exhaustive so a Saturday founder can flip the switch
and run the full 12-case matrix to validate the layer end-to-end.

Coverage strategy:
    create / get_by_id / list_pending / mark_running / mark_succeeded /
    mark_failed — at least one happy-path test each, plus the
    "concurrent-loser returns 0 rows" path for each mark_*.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.historical_backfill_job import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
)
from app.services.historical_candles.jobs_repository import (
    HistoricalBackfillJobsRepository,
)

# Migration 030 applied 2026-06-13 (founder gate Saturday morning).
# Tests now run end-to-end against the live historical_backfill_jobs table.


_BASE_TS = datetime(2026, 6, 12, 3, 45, tzinfo=UTC)


def _job_kwargs(symbol: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "exchange": "NSE_EQ",
        "timeframe": "5m",
        "dhan_security_id": "999",
        "from_ts": _BASE_TS,
        "to_ts": _BASE_TS + timedelta(hours=1),
    }


# ═══════════════════════════════════════════════════════════════════════
# create + get_by_id + list_pending
# ═══════════════════════════════════════════════════════════════════════


async def test_create__inserts_pending_job(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    job = await repo.create(**_job_kwargs(test_symbol_prefix))
    assert job.id is not None
    assert job.status == STATUS_PENDING
    assert job.started_at is None
    assert job.completed_at is None
    assert job.candles_inserted == 0
    assert job.attempt_count == 0


async def test_get_by_id__round_trips(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    created = await repo.create(**_job_kwargs(test_symbol_prefix))
    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.symbol == test_symbol_prefix


async def test_get_by_id__missing_returns_none(
    db_session: AsyncSession,
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    assert await repo.get_by_id(uuid.uuid4()) is None


async def test_list_pending__fifo_by_requested_at(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    j1 = await repo.create(**_job_kwargs(f"{test_symbol_prefix}_A"))
    j2 = await repo.create(**_job_kwargs(f"{test_symbol_prefix}_B"))
    pending = await repo.list_pending(limit=10)
    ids = [j.id for j in pending]
    assert j1.id in ids and j2.id in ids
    # j1 was requested before j2 → must come first
    assert ids.index(j1.id) < ids.index(j2.id)


async def test_list_pending__limit_respected(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    for i in range(3):
        await repo.create(**_job_kwargs(f"{test_symbol_prefix}_{i}"))
    rows = await repo.list_pending(limit=2)
    assert len(rows) == 2


# ═══════════════════════════════════════════════════════════════════════
# mark_running
# ═══════════════════════════════════════════════════════════════════════


async def test_mark_running__transitions_pending_to_running(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    job = await repo.create(**_job_kwargs(test_symbol_prefix))
    rows = await repo.mark_running(job.id, quota_rationale="off_market")
    assert rows == 1
    refetched = await repo.get_by_id(job.id)
    assert refetched.status == STATUS_RUNNING
    assert refetched.started_at is not None
    assert refetched.quota_rationale_at_start == "off_market"
    assert refetched.attempt_count == 1


async def test_mark_running__non_pending_returns_zero(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    job = await repo.create(**_job_kwargs(test_symbol_prefix))
    await repo.mark_running(job.id, quota_rationale="off_market")
    # Second call (already RUNNING) → 0 rows.
    rows = await repo.mark_running(job.id, quota_rationale="off_market")
    assert rows == 0


# ═══════════════════════════════════════════════════════════════════════
# mark_succeeded
# ═══════════════════════════════════════════════════════════════════════


async def test_mark_succeeded__from_running(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    job = await repo.create(**_job_kwargs(test_symbol_prefix))
    await repo.mark_running(job.id, quota_rationale="off_market")
    rows = await repo.mark_succeeded(job.id, candles_inserted=42)
    assert rows == 1
    refetched = await repo.get_by_id(job.id)
    assert refetched.status == STATUS_SUCCEEDED
    assert refetched.completed_at is not None
    assert refetched.candles_inserted == 42


async def test_mark_succeeded__from_pending_is_noop(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    job = await repo.create(**_job_kwargs(test_symbol_prefix))
    rows = await repo.mark_succeeded(job.id, candles_inserted=42)
    assert rows == 0


# ═══════════════════════════════════════════════════════════════════════
# mark_failed
# ═══════════════════════════════════════════════════════════════════════


async def test_mark_failed__from_running(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    job = await repo.create(**_job_kwargs(test_symbol_prefix))
    await repo.mark_running(job.id, quota_rationale="off_market")
    err = {"type": "BrokerRateLimitError", "message": "5 req/s exceeded"}
    rows = await repo.mark_failed(job.id, error=err)
    assert rows == 1
    refetched = await repo.get_by_id(job.id)
    assert refetched.status == STATUS_FAILED
    assert refetched.completed_at is not None
    assert refetched.error_json == err


async def test_mark_failed__from_pending_is_noop(
    db_session: AsyncSession, test_symbol_prefix: str
) -> None:
    repo = HistoricalBackfillJobsRepository(db_session)
    job = await repo.create(**_job_kwargs(test_symbol_prefix))
    rows = await repo.mark_failed(
        job.id, error={"type": "X", "message": "y"}
    )
    assert rows == 0
