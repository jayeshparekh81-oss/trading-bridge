"""Celery tasks for async notification dispatch.

These tasks run outside the FastAPI request cycle so notification latency
does not block order execution.
"""

from __future__ import annotations

from typing import Any

from app.core.async_bridge import run_async as _run
from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger("app.tasks.notification")

# ``_run`` is the shared :func:`app.core.async_bridge.run_async` (imported
# above) — one persistent event loop per worker process, replacing the previous
# per-task fresh-loop helper. See async_bridge for the rationale
# (incident 2026-05-24).


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification_task(
    self: Any,
    user_id: str,
    event_type: str,
    context: dict[str, Any],
) -> dict[str, str]:
    """Async notification dispatch. Retries 3x with 30s delay."""
    from uuid import UUID

    try:
        from app.db.session import get_sessionmaker
        from app.services.notification_service import notification_service

        async def _send() -> dict[str, str]:
            maker = get_sessionmaker()
            async with maker() as session:
                return await notification_service.send(
                    user_id=UUID(user_id),
                    event_type=event_type,
                    context=context,
                    db=session,
                )

        return _run(_send())
    except Exception as exc:
        logger.warning(
            "notification_task.failed",
            user_id=user_id,
            event_type=event_type,
            error=str(exc),
        )
        raise self.retry(exc=exc) from exc


@celery_app.task
def send_daily_summary_all() -> int:
    """16:00 IST — Send daily summary to all active users."""

    from sqlalchemy import select

    from app.db.models.user import User
    from app.db.session import get_sessionmaker
    from app.services.notification_service import notification_service

    async def _send_all() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            stmt = select(User).where(User.is_active.is_(True))
            result = await session.execute(stmt)
            users = result.scalars().all()
            count = 0
            for user in users:
                try:
                    await notification_service.send(
                        user_id=user.id,
                        event_type="daily_summary",
                        context={"message": "Your daily trading summary"},
                        db=session,
                    )
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "daily_summary.user_failed",
                        user_id=str(user.id),
                        error=str(exc),
                    )
            return count

    sent = _run(_send_all())
    logger.info("daily_summary.complete", users_notified=sent)
    return sent


@celery_app.task
def send_weekly_report_all() -> int:
    """Sunday 18:00 IST — Weekly performance report."""
    from sqlalchemy import select

    from app.db.models.user import User
    from app.db.session import get_sessionmaker
    from app.services.notification_service import notification_service

    async def _send_all() -> int:
        maker = get_sessionmaker()
        async with maker() as session:
            stmt = select(User).where(User.is_active.is_(True))
            result = await session.execute(stmt)
            users = result.scalars().all()
            count = 0
            for user in users:
                try:
                    await notification_service.send(
                        user_id=user.id,
                        event_type="weekly_report",
                        context={"message": "Your weekly performance report"},
                        db=session,
                    )
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "weekly_report.user_failed",
                        user_id=str(user.id),
                        error=str(exc),
                    )
            return count

    sent = _run(_send_all())
    logger.info("weekly_report.complete", users_notified=sent)
    return sent


__all__ = ["send_daily_summary_all", "send_notification_task", "send_weekly_report_all"]


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_operator_alert_task(self: Any, level_value: str, message: str) -> str:
    """Operator Telegram alert, dispatched OFF the request path.

    WHY (2026-08-28): strategy_webhook awaited telegram_alerts.send_alert INLINE inside the
    Market Strength Shield branches, i.e. a Telegram HTTP call in front of the 202 that accepts
    an order. A notification is not part of accepting an order. This module already existed for
    exactly this ("so notification latency does not block order execution"); the shield alerts
    simply were not using it.

    QUEUED, NOT FIRE-AND-FORGET, deliberately: Redis runs appendonly, so a queued alert survives
    a backend restart. An asyncio.create_task would not, and this box has a history of alerts
    that were silently never sent.

    🔴 HONEST LIMIT OF THE RETRY. telegram_alerts.send_alert swallows its own transport errors
    and always returns None, so a Telegram HTTP failure is INVISIBLE here and retry cannot see
    it (send_alert logs its own warning). The retry therefore covers TASK-level failure -- import
    error, worker crash, event-loop failure -- not a failed Telegram send. The one silent-drop
    path this CAN see is a missing chat id, which send_alert treats as a no-op return; that is
    escalated to ERROR below rather than returning quietly.
    """
    try:
        from app.core.config import get_settings
        from app.services import telegram_alerts as _alerts

        if not get_settings().telegram_alert_chat_id:
            logger.error(
                "operator_alert.DROPPED_no_chat_id",
                level=level_value,
                preview=message[:160],
            )
            return "dropped_no_chat_id"

        _run(_alerts.send_alert(_alerts.AlertLevel(level_value), message))
        logger.info("operator_alert.dispatched", level=level_value, preview=message[:160])
        return "dispatched"
    except Exception as exc:
        logger.warning(
            "operator_alert.attempt_failed",
            level=level_value, error=str(exc), retries=self.request.retries,
        )
        if self.request.retries >= self.max_retries:
            logger.error(
                "operator_alert.GAVE_UP_alert_never_sent",
                level=level_value, error=str(exc), preview=message[:160],
            )
        raise self.retry(exc=exc) from exc
