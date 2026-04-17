"""Celery tasks for async notification dispatch.

These tasks run outside the FastAPI request cycle so notification latency
does not block order execution.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger("app.tasks.notification")


def _run(coro: Any) -> Any:
    """Run an async coroutine in a fresh event loop (Celery workers are sync)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    return asyncio.run(coro)


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
