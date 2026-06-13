"""Async repository for ``historical_backfill_jobs``.

Single owner of the state-machine transitions for a backfill job. The
Celery task asks ``list_pending``, takes ownership with ``mark_running``
(which sets ``started_at`` + records the rate-limit-guard rationale),
runs the orchestrator, then finalises with either ``mark_succeeded`` or
``mark_failed``.

Lifecycle invariants are enforced at the DB layer (see migration 030
CHECK constraints) — the repository's mark_* helpers always emit
matching column updates, so any drift between repo logic and schema is
caught at the constraint instead of silently corrupting state.

Logging: one structured INFO line per state transition + one structured
ERROR on caught exceptions inside ``mark_failed``. Reads stay silent.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.historical_backfill_job import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    HistoricalBackfillJob,
)

logger = logging.getLogger(__name__)


class HistoricalBackfillJobsRepository:
    """Async wrapper around the ``historical_backfill_jobs`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        dhan_security_id: str,
        from_ts: datetime,
        to_ts: datetime,
        requested_by_user_id: uuid.UUID | None = None,
    ) -> HistoricalBackfillJob:
        """Insert a PENDING job. Returns the persisted row.

        Caller commits — the repo never owns the transaction boundary.
        """
        job = HistoricalBackfillJob(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            dhan_security_id=dhan_security_id,
            from_ts=from_ts,
            to_ts=to_ts,
            requested_by_user_id=requested_by_user_id,
        )
        self._session.add(job)
        await self._session.flush()
        logger.info(
            json.dumps(
                {
                    "event": "historical_backfill_jobs.create",
                    "job_id": str(job.id),
                    "symbol": symbol,
                    "exchange": exchange,
                    "timeframe": timeframe,
                }
            )
        )
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> HistoricalBackfillJob | None:
        return (
            await self._session.execute(
                select(HistoricalBackfillJob).where(HistoricalBackfillJob.id == job_id)
            )
        ).scalar_one_or_none()

    async def list_pending(self, limit: int = 10) -> list[HistoricalBackfillJob]:
        """PENDING jobs ordered FIFO by ``requested_at``.

        Limit is mandatory (default 10) so a single beat tick never
        drains the whole queue in one transaction.
        """
        stmt = (
            select(HistoricalBackfillJob)
            .where(HistoricalBackfillJob.status == STATUS_PENDING)
            .order_by(HistoricalBackfillJob.requested_at.asc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def mark_running(
        self,
        job_id: uuid.UUID,
        *,
        quota_rationale: str,
    ) -> int:
        """Transition PENDING → RUNNING. Records the rate-limit
        rationale that authorised the start for later audit.

        Returns the number of rows updated (1 on success, 0 if the
        row was concurrently taken by another worker — caller treats
        0 as "another worker won, skip this job").
        """
        now = datetime.now(UTC)
        stmt = (
            update(HistoricalBackfillJob)
            .where(
                HistoricalBackfillJob.id == job_id,
                HistoricalBackfillJob.status == STATUS_PENDING,
            )
            .values(
                status=STATUS_RUNNING,
                started_at=now,
                quota_rationale_at_start=quota_rationale,
                attempt_count=HistoricalBackfillJob.attempt_count + 1,
            )
        )
        result = await self._session.execute(stmt)
        rows = result.rowcount or 0
        logger.info(
            json.dumps(
                {
                    "event": "historical_backfill_jobs.mark_running",
                    "job_id": str(job_id),
                    "rows_updated": rows,
                    "quota_rationale": quota_rationale,
                }
            )
        )
        return rows

    async def mark_succeeded(
        self,
        job_id: uuid.UUID,
        *,
        candles_inserted: int,
    ) -> int:
        """Transition RUNNING → SUCCEEDED with bar-count audit."""
        now = datetime.now(UTC)
        stmt = (
            update(HistoricalBackfillJob)
            .where(
                HistoricalBackfillJob.id == job_id,
                HistoricalBackfillJob.status == STATUS_RUNNING,
            )
            .values(
                status=STATUS_SUCCEEDED,
                completed_at=now,
                candles_inserted=candles_inserted,
            )
        )
        result = await self._session.execute(stmt)
        rows = result.rowcount or 0
        logger.info(
            json.dumps(
                {
                    "event": "historical_backfill_jobs.mark_succeeded",
                    "job_id": str(job_id),
                    "candles_inserted": candles_inserted,
                    "rows_updated": rows,
                }
            )
        )
        return rows

    async def mark_failed(
        self,
        job_id: uuid.UUID,
        *,
        error: dict[str, Any],
    ) -> int:
        """Transition RUNNING → FAILED with structured error payload.

        ``error`` is a free-form dict (caller-shaped — typically
        ``{"type": exc.__class__.__name__, "message": str(exc),
        "traceback_first_line": ...}``). Stored in ``error_json`` and
        also emitted as a structured ERROR log.
        """
        now = datetime.now(UTC)
        stmt = (
            update(HistoricalBackfillJob)
            .where(
                HistoricalBackfillJob.id == job_id,
                HistoricalBackfillJob.status == STATUS_RUNNING,
            )
            .values(
                status=STATUS_FAILED,
                completed_at=now,
                error_json=error,
            )
        )
        result = await self._session.execute(stmt)
        rows = result.rowcount or 0
        logger.error(
            json.dumps(
                {
                    "event": "historical_backfill_jobs.mark_failed",
                    "job_id": str(job_id),
                    "rows_updated": rows,
                    "error_type": error.get("type"),
                    "error_message_excerpt": (str(error.get("message", ""))[:160]),
                }
            )
        )
        return rows


__all__ = ["HistoricalBackfillJobsRepository"]
