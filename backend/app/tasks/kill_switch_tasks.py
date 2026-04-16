"""Scheduled + on-demand tasks feeding the kill-switch and cleanup jobs.

Every task is a thin sync wrapper around an async coroutine so Celery's
prefork model works without a custom event loop. We open a fresh DB
session per task — the request-scoped session from FastAPI isn't usable
here.

Error policy
------------
Tasks catch and log exceptions instead of ``raise`` — Celery's retry
machinery is best for transient network issues, but a runtime error in
emergency-square-off should not mask the partial progress we already
made (brokers we did reach, etc.). The caller (beat) logs the return
value so the pipeline stays observable even when a single branch fails.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time
from typing import Any
from uuid import UUID

from celery import shared_task

from app.core.logging import get_logger


logger = get_logger("app.tasks.kill_switch")


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _run(coro: Any) -> Any:
    """Run an async coroutine in a fresh event loop for a Celery worker.

    When called from a thread that already has a running loop (e.g. a
    pytest-asyncio test invoking an eager task), we cannot use
    ``run_until_complete`` on the active loop — do the work in a helper
    thread that owns its own loop. Celery workers run sync so the fast
    path just spins up a fresh loop.
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    try:
        if running is None:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        # Active loop present → run in a helper thread with its own loop.
        import threading

        result_holder: dict[str, Any] = {}

        def _target() -> None:
            new_loop = asyncio.new_event_loop()
            try:
                result_holder["value"] = new_loop.run_until_complete(coro)
            except BaseException as exc:  # noqa: BLE001
                result_holder["error"] = exc
            finally:
                new_loop.close()

        thread = threading.Thread(target=_target)
        thread.start()
        thread.join()
        if "error" in result_holder:
            raise result_holder["error"]
        return result_holder.get("value")
    except Exception as exc:  # noqa: BLE001 — task-level safety net
        logger.warning("task.failed", error=str(exc))
        raise


# ═══════════════════════════════════════════════════════════════════════
# Core tasks
# ═══════════════════════════════════════════════════════════════════════


@shared_task(name="app.tasks.kill_switch_tasks.execute_emergency_square_off",
             autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def execute_emergency_square_off(user_id: str) -> dict[str, Any]:
    """Re-run the kill-switch firing in the background.

    Called when the webhook detects a breach but wants to hand the actual
    broker work to a worker so the HTTP response isn't held up. The
    webhook has already set the Redis TRIPPED flag; this task only does
    the broker-side cleanup.
    """
    async def _go() -> dict[str, Any]:
        from app.db.session import get_sessionmaker
        from app.schemas.kill_switch import TripReason
        from app.services.kill_switch_service import kill_switch_service

        maker = get_sessionmaker()
        async with maker() as session:
            result = await kill_switch_service.check_and_trigger(
                UUID(user_id),
                session,
                force_reason=TripReason.DAILY_LOSS_BREACHED,
            )
            await session.commit()
            return result.model_dump(mode="json")

    return _run(_go())


@shared_task(name="app.tasks.kill_switch_tasks.daily_pnl_reset")
def daily_pnl_reset() -> dict[str, Any]:
    """09:00 IST — wipe per-user day counters."""
    async def _go() -> dict[str, Any]:
        from app.db.session import get_sessionmaker
        from app.services.kill_switch_service import kill_switch_service

        maker = get_sessionmaker()
        async with maker() as session:
            removed = await kill_switch_service.daily_reset_all(session)
            await session.commit()
            return {"keys_removed": removed}

    return _run(_go())


@shared_task(name="app.tasks.kill_switch_tasks.auto_square_off_intraday")
def auto_square_off_intraday() -> dict[str, Any]:
    """15:15 IST — close every intraday position for opted-in users."""
    async def _go() -> dict[str, Any]:
        from app.db.session import get_sessionmaker
        from app.services.kill_switch_service import kill_switch_service

        maker = get_sessionmaker()
        async with maker() as session:
            touched = await kill_switch_service.auto_square_off_intraday(session)
            await session.commit()
            return {"users_touched": [str(u) for u in touched]}

    return _run(_go())


@shared_task(name="app.tasks.kill_switch_tasks.check_market_status")
def check_market_status() -> dict[str, Any]:
    """Cache ``market_status`` in Redis every minute (open / closed).

    Kept cheap — no DB, no broker call. Strategies consult this flag to
    decide whether a webhook that arrives outside hours should queue or
    reject.
    """
    async def _go() -> dict[str, Any]:
        from app.core import redis_client

        now_utc = datetime.now(UTC)
        # IST window: 09:15 – 15:30 → UTC 03:45 – 10:00
        open_utc = time(3, 45)
        close_utc = time(10, 0)
        is_weekday = now_utc.weekday() < 5
        in_hours = open_utc <= now_utc.time() <= close_utc
        status = "open" if is_weekday and in_hours else "closed"
        client = redis_client.get_redis()
        await client.set("market:status", status, ex=120)
        return {"status": status, "checked_at": now_utc.isoformat()}

    return _run(_go())


@shared_task(name="app.tasks.kill_switch_tasks.cleanup_expired_sessions")
def cleanup_expired_sessions() -> dict[str, Any]:
    """Sweep ``session_blacklist:*`` entries whose TTL hit zero.

    Redis expires them automatically; this task counts them for ops
    dashboards and clears any orphaned entries.
    """
    async def _go() -> dict[str, Any]:
        from app.core import redis_client

        client = redis_client.get_redis()
        scanned = 0
        removed = 0
        async for key in client.scan_iter(match="session_blacklist:*", count=200):
            scanned += 1
            ttl = await client.ttl(key)
            if ttl in (-2, -1):
                await client.delete(key)
                removed += 1
        return {"scanned": scanned, "removed": removed}

    return _run(_go())


@shared_task(name="app.tasks.kill_switch_tasks.rotate_idempotency_keys")
def rotate_idempotency_keys() -> dict[str, Any]:
    """Remove expired rows from ``idempotency_keys`` (DB-side)."""
    async def _go() -> dict[str, Any]:
        from app.db.session import get_sessionmaker
        from app.services.kill_switch_service import delete_expired_idempotency

        maker = get_sessionmaker()
        async with maker() as session:
            removed = await delete_expired_idempotency(session)
            await session.commit()
            return {"rows_removed": removed}

    return _run(_go())


@shared_task(name="app.tasks.kill_switch_tasks.send_kill_switch_notification")
def send_kill_switch_notification(user_id: str, event_data: dict[str, Any]) -> dict[str, Any]:
    """Queue a user-facing alert (email + Telegram).

    Step 5 stops at queueing — actual transports land in the notifications
    module. Returns the would-be payload so integration tests can assert.
    """
    payload = {
        "user_id": user_id,
        "event": event_data,
        "channels": ["email", "telegram"],
    }
    logger.info("notify.kill_switch_queued", **{k: v for k, v in payload.items() if k != "event"})
    return payload


@shared_task(name="app.tasks.kill_switch_tasks.generate_daily_trade_report")
def generate_daily_trade_report(user_id: str | None = None) -> dict[str, Any]:
    """Build a daily summary and cache it under ``report:daily:{user_id}:{date}``.

    Invoked globally by beat at 16:00 IST, but also callable per-user by
    admins. When called without ``user_id`` it iterates every user with
    a kill-switch config row (operator scope).
    """
    async def _go() -> dict[str, Any]:
        from app.core import redis_client
        from app.db.models.kill_switch import KillSwitchConfig
        from app.db.session import get_sessionmaker
        from app.services.kill_switch_service import kill_switch_service
        from sqlalchemy import select

        maker = get_sessionmaker()
        today = datetime.now(UTC).date().isoformat()
        produced: list[str] = []
        async with maker() as session:
            if user_id:
                targets = [UUID(user_id)]
            else:
                rows = (
                    await session.execute(select(KillSwitchConfig.user_id))
                ).scalars().all()
                targets = list(rows)

            for uid in targets:
                summary = await kill_switch_service.get_daily_summary(uid, session)
                await redis_client.cache_set_json(
                    f"report:daily:{uid}:{today}",
                    summary.model_dump(mode="json"),
                    ttl_seconds=7 * 24 * 3600,
                )
                produced.append(str(uid))
        return {"date": today, "users": produced}

    return _run(_go())


__all__ = [
    "auto_square_off_intraday",
    "check_market_status",
    "cleanup_expired_sessions",
    "daily_pnl_reset",
    "execute_emergency_square_off",
    "generate_daily_trade_report",
    "rotate_idempotency_keys",
    "send_kill_switch_notification",
]
