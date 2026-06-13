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


# ═══════════════════════════════════════════════════════════════════════
# A5 — Dhan credential factory (Queue FFF)
# ═══════════════════════════════════════════════════════════════════════

# Sentinel UUID used as ``user_id`` when service-account env-direct creds
# are in play (per-user rate-limit keying inside DhanHistoricalClient
# still requires a UUID; this is distinct from any real user). Sister to
# ``_SMOKE_TEST_USER_ID = …0001`` in
# ``scripts/manual_test_phase2c_dhan_nifty50.py``.
_BACKFILL_SERVICE_ACCOUNT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _service_account_user_id() -> uuid.UUID | None:
    """Read ``BACKFILL_DHAN_USER_ID`` env var (service-account beta path).

    Returns the UUID when set + parseable; None otherwise (unset, empty,
    or invalid format). Invalid format is logged at WARNING but does
    NOT raise — caller falls through to env-direct (alpha) or error.
    """
    raw = os.environ.get("BACKFILL_DHAN_USER_ID", "").strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError):
        logger.warning(
            json.dumps(
                {
                    "event": "backfill_dhan_user_id_invalid",
                    "raw_length": len(raw),
                }
            )
        )
        return None


def _env_direct_creds() -> tuple[str, str] | None:
    """Read ``BACKFILL_DHAN_CLIENT_ID`` + ``BACKFILL_DHAN_ACCESS_TOKEN``
    env vars (service-account alpha path).

    Returns ``(client_id, access_token)`` only when BOTH are set
    non-empty. Partial config (one set, the other not) is treated as
    not-configured — defensive against half-rotated env in operator
    typos.
    """
    client_id = os.environ.get("BACKFILL_DHAN_CLIENT_ID", "").strip()
    access_token = os.environ.get("BACKFILL_DHAN_ACCESS_TOKEN", "").strip()
    if client_id and access_token:
        return client_id, access_token
    return None


async def _lookup_user_dhan_creds(
    session, user_id: uuid.UUID, *, source: str
) -> tuple[str, str, uuid.UUID]:
    """Look up + decrypt the most-recent active Dhan ``BrokerCredential``
    for ``user_id``.

    Wraps decryption failures in :class:`BrokerAuthError` per Q3 — the
    Celery task layer expects ``BrokerAuthError``-shaped failures from
    the credential layer.

    Logs one structured INFO line on success (no secret content); the
    ``source`` token records which resolver branch authorised the
    lookup for the audit trail.
    """
    from sqlalchemy import select

    from app.brokers.dhan_historical import BrokerAuthError
    from app.core.security import decrypt_credential
    from app.db.models.broker_credential import BrokerCredential
    from app.schemas.broker import BrokerName

    stmt = (
        select(BrokerCredential)
        .where(
            BrokerCredential.user_id == user_id,
            BrokerCredential.broker_name == BrokerName.DHAN,
            BrokerCredential.is_active.is_(True),
        )
        .order_by(BrokerCredential.created_at.desc())
        .limit(1)
    )
    cred = (await session.execute(stmt)).scalar_one_or_none()
    if cred is None:
        raise BrokerAuthError(
            f"No active Dhan BrokerCredential for user {user_id} (source={source})."
        )
    if cred.access_token_enc is None:
        raise BrokerAuthError(f"Dhan access_token not stored for user {user_id} (source={source}).")
    try:
        client_id = decrypt_credential(cred.client_id_enc)
        access_token = decrypt_credential(cred.access_token_enc)
    except Exception as exc:
        raise BrokerAuthError(
            f"Dhan credential decryption failed for user {user_id} "
            f"(source={source}): {exc.__class__.__name__}"
        ) from exc

    logger.info(
        json.dumps(
            {
                "event": "dhan_creds_resolved",
                "source": source,
                "user_id": str(user_id),
            }
        )
    )
    return client_id, access_token, user_id


async def _resolve_dhan_creds(session, job) -> tuple[str, str, uuid.UUID]:
    """Three-tier resolver for the Dhan credentials a backfill job needs.

    Decision tree:
      1. ``job.requested_by_user_id`` is set → look up that user's cred
         (per-user path).
      2. Else if ``BACKFILL_DHAN_USER_ID`` env is set → look up that
         UUID's cred (service-account beta, DB-backed).
      3. Else if ``BACKFILL_DHAN_CLIENT_ID`` + ``BACKFILL_DHAN_ACCESS_TOKEN``
         env BOTH set → use env values directly (service-account alpha,
         dev convenience). ``user_id`` for rate-limit keying is the
         :data:`_BACKFILL_SERVICE_ACCOUNT_USER_ID` sentinel.
      4. Otherwise → :class:`BrokerAuthError`.

    beta + alpha both set + no per-user → beta wins. Per-user always beats both
    service-account paths.
    """
    from app.brokers.dhan_historical import BrokerAuthError

    if job.requested_by_user_id is not None:
        return await _lookup_user_dhan_creds(session, job.requested_by_user_id, source="per_user")

    service_user = _service_account_user_id()
    if service_user is not None:
        return await _lookup_user_dhan_creds(session, service_user, source="service_account_db")

    env_creds = _env_direct_creds()
    if env_creds is not None:
        client_id, access_token = env_creds
        logger.info(
            json.dumps(
                {
                    "event": "dhan_creds_resolved",
                    "source": "service_account_env",
                    "user_id": str(_BACKFILL_SERVICE_ACCOUNT_USER_ID),
                }
            )
        )
        return client_id, access_token, _BACKFILL_SERVICE_ACCOUNT_USER_ID

    raise BrokerAuthError(
        "No Dhan credentials configured: job has no requested_by_user_id, "
        "BACKFILL_DHAN_USER_ID env unset, and BACKFILL_DHAN_CLIENT_ID + "
        "BACKFILL_DHAN_ACCESS_TOKEN env not both set."
    )


def _dhan_client_factory_for_job(job):
    """Factory closure that returns a configured DhanHistoricalClient.

    Resolves Dhan credentials per the three-tier fallback in
    :func:`_resolve_dhan_creds` (per-user → service-account-DB →
    service-account-env) and builds a ready
    :class:`DhanHistoricalClient`.

    The factory opens its own short-lived session for the credential
    read so it doesn't share state with the main task's session. The
    lookup is read-only; nothing is written to the DB from this path.

    Reachable only behind ``BACKFILL_ENABLED=true`` (which defaults
    OFF). The BSE LTD live strategy is untouched by this code path —
    backfill operates on the ``historical_candles`` store, not on any
    live-execution surface.

    Raises:
        BrokerAuthError: when no Dhan credentials can be resolved for
            the job. Caller (the Celery task) catches this and calls
            ``mark_failed`` with the truncated error message.
    """

    async def _factory():
        from app.brokers.dhan_historical import DhanHistoricalClient
        from app.db.session import get_sessionmaker

        maker = get_sessionmaker()
        async with maker() as session:
            client_id, access_token, user_id = await _resolve_dhan_creds(session, job)
        return DhanHistoricalClient(
            client_id=client_id,
            access_token=access_token,
            user_id=user_id,
        )

    return _factory


__all__ = ["backfill_one_job"]
