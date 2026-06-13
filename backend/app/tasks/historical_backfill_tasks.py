"""Celery task entry-point for the Phase 3 historical-candles backfill.

**Feature-flagged OFF by default** per design v2 Q4A: until the
founder explicitly flips ``BACKFILL_ENABLED=true`` in the worker
environment, every task invocation short-circuits with a structured
log line and returns ``{"status": "disabled"}``. This lets us
register the task module and exercise the surface in tests without
risking an accidental Dhan call.

Why ``@shared_task`` rather than ``@celery_app.task``:
    Following the precedent set by
    ``app.backtest_extension.celery_tasks``. ``@shared_task``
    registers against whichever Celery app is active at import time,
    which keeps the task module decoupled from
    ``app.tasks.celery_app`` and avoids a tight import cycle. Worker
    auto-discovery still needs the module to be listed in
    ``celery_app._build_celery().include`` — that one-line addition
    is captured in the overnight brief's morning-gate diff because
    editing ``celery_app.py`` is off-limits tonight.

Per-task duties:
    1. Read the feature flag. If OFF: log + return early.
    2. Look up the :class:`HistoricalBackfillJob` row by id.
    3. Consult :func:`rate_limit_guard.compute_backfill_quota` —
       record the rationale token onto the row at ``mark_running``.
    4. Run the orchestrator, which chunks the window, fetches via
       :class:`DhanHistoricalClient`, bridges, and persists.
    5. Finalise via ``mark_succeeded`` / ``mark_failed``.

What is NOT in this skeleton:
    * **Dhan credential resolution.** Phase 3 follow-up — the task
      needs a per-user :class:`BrokerCredential` lookup or a
      service-account fallback. Marked as TODO; current code raises
      ``NotImplementedError`` when credentials would be needed,
      reaching it only behind the OFF feature flag.
    * **Retry policy.** Celery autoretry / max_retries config. The
      jobs table already tracks ``attempt_count``; we'll wire the
      decorator config in the same follow-up.
    * **Beat schedule.** The Celery-beat entry that hands the
      pending queue to this task lives in
      ``app.tasks.celery_app.beat_schedule`` (existing file) — its
      diff is in the overnight brief.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import UTC, datetime

from celery import shared_task

logger = logging.getLogger(__name__)


def _backfill_enabled() -> bool:
    """Read ``BACKFILL_ENABLED`` env var. Default OFF.

    Truthy values: ``true``, ``1``, ``yes`` (case-insensitive).
    Everything else (including missing) → False.
    """
    raw = os.environ.get("BACKFILL_ENABLED", "false")
    return raw.strip().lower() in ("true", "1", "yes")


def _log_disabled(job_id: str) -> dict[str, str]:
    payload = {
        "status": "disabled",
        "reason": "BACKFILL_ENABLED feature flag is false (default).",
        "job_id": job_id,
    }
    logger.info(
        json.dumps(
            {
                "event": "historical_backfill.task_skipped_flag_off",
                **payload,
            }
        )
    )
    return payload


@shared_task(name="historical_candles.backfill_one_job")
def backfill_one_job(job_id: str) -> dict[str, object]:
    """Process a single backfill job.

    Args:
        job_id: UUID string identifying the row in
            ``historical_backfill_jobs``.

    Returns:
        A dict describing the outcome. Shape:
            ``{"status": "disabled" | "succeeded" | "failed" | "skipped", …}``

    The Celery-task wrapper around an asyncio coroutine: Celery
    workers are sync, so we ``asyncio.run`` the async body. Each
    invocation gets its own event loop — keeps the SQLAlchemy
    asyncpg engine pool clean.
    """
    if not _backfill_enabled():
        return _log_disabled(job_id)
    return asyncio.run(_run_one(job_id))


async def _run_one(job_id_str: str) -> dict[str, object]:
    """Async task body. Importable directly for unit tests.

    Imports are localised so that the module-level Celery decorator
    can be imported without paying the cost of the SQLAlchemy + Dhan
    client imports until the flag is actually ON.
    """
    from app.db.session import dispose_engine, get_sessionmaker
    from app.services.historical_candles.jobs_repository import (
        HistoricalBackfillJobsRepository,
    )
    from app.services.historical_candles.orchestrator import (
        HistoricalCandleOrchestrator,
    )
    from app.services.historical_candles.rate_limit_guard import (
        compute_backfill_quota,
    )
    from app.services.historical_candles.repository import (
        HistoricalCandleRepository,
    )

    job_id = uuid.UUID(job_id_str)
    maker = get_sessionmaker()

    async with maker() as session:
        jobs_repo = HistoricalBackfillJobsRepository(session)
        job = await jobs_repo.get_by_id(job_id)
        if job is None:
            logger.info(
                json.dumps(
                    {
                        "event": "historical_backfill.job_not_found",
                        "job_id": str(job_id),
                    }
                )
            )
            return {"status": "skipped", "reason": "job_not_found"}

        # Kill-switch state lookup is Phase 3+ follow-up; conservative
        # default is False (not paused) so the live-market 20% applies
        # during market hours.
        kill_switch_paused_live = False
        quota = compute_backfill_quota(
            now_utc=datetime.now(UTC),
            kill_switch_paused_live=kill_switch_paused_live,
        )

        claimed = await jobs_repo.mark_running(job_id, quota_rationale=quota.rationale)
        if claimed == 0:
            return {"status": "skipped", "reason": "concurrent_claim_lost"}
        await session.commit()

        try:
            repo = HistoricalCandleRepository(session)
            orchestrator = HistoricalCandleOrchestrator(
                repository=repo,
                client_factory=_dhan_client_factory_for_job(job),
            )
            from app.schemas.candle import Timeframe

            report = await orchestrator.fetch_and_persist(
                symbol=job.symbol,
                exchange=job.exchange,
                security_id=job.dhan_security_id,
                instrument="EQUITY",  # Phase 3+ — resolve per scrip master
                timeframe=Timeframe(job.timeframe),
                from_ts=job.from_ts,
                to_ts=job.to_ts,
                fetched_by_user_id=job.requested_by_user_id,
            )
            await jobs_repo.mark_succeeded(job_id, candles_inserted=report.bars_inserted)
            await session.commit()
            return {
                "status": "succeeded",
                "job_id": str(job_id),
                "bars_inserted": report.bars_inserted,
                "bars_fetched": report.bars_fetched,
                "quality_avg": str(report.quality_score_avg),
            }
        except Exception as exc:
            payload = {
                "type": exc.__class__.__name__,
                "message": str(exc)[:512],
            }
            await jobs_repo.mark_failed(job_id, error=payload)
            await session.commit()
            return {
                "status": "failed",
                "job_id": str(job_id),
                "error_type": payload["type"],
            }
        finally:
            await dispose_engine()


def _dhan_client_factory_for_job(job):  # pragma: no cover — Phase 3+
    """Factory closure that returns a configured DhanHistoricalClient.

    Phase 3+ follow-up: this is where per-user credential lookup will
    live. Tonight's skeleton raises ``NotImplementedError`` deliberately
    — the path can ONLY be reached when ``BACKFILL_ENABLED=true``,
    which the founder will set only after the credential resolver
    lands. Tests stub this whole function out.
    """

    async def _factory():
        raise NotImplementedError(
            "Dhan credential resolution is a Phase 3+ follow-up. "
            "Set BACKFILL_ENABLED=true only after the credential "
            "resolver is wired in."
        )

    return _factory


__all__ = ["backfill_one_job"]
