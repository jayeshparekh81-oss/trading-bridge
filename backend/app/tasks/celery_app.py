"""Celery factory + beat schedule.

Kept out of :mod:`app.main` so importing the FastAPI app does not pull
Celery into every request path. ``celery_app`` here is the singleton;
task modules decorate with ``@celery_app.task``.

Beat schedule is IST-referenced in comments and UTC-referenced in the
crontab arguments — that split is deliberate so the schedule object stays
timezone-free and our ops runbooks can use IST directly.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings


def _build_celery() -> Celery:
    settings = get_settings()
    broker = getattr(settings, "celery_broker_url", settings.redis_url)
    backend = getattr(settings, "celery_result_backend", settings.redis_url)

    app = Celery(
        "trading_bridge",
        broker=broker,
        backend=backend,
        include=[
            "app.tasks.kill_switch_tasks",
        ],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        # Retries — transient broker failures should not surface as job loss.
        task_default_retry_delay=30,
        task_annotations={"*": {"max_retries": 3}},
    )
    # Beat schedule. IST = UTC + 5:30. Comments show IST wall-clock time.
    app.conf.beat_schedule = {
        "daily-pnl-reset": {
            # 09:00 IST → 03:30 UTC
            "task": "app.tasks.kill_switch_tasks.daily_pnl_reset",
            "schedule": crontab(hour=3, minute=30),
        },
        "auto-square-off": {
            # 15:15 IST → 09:45 UTC
            "task": "app.tasks.kill_switch_tasks.auto_square_off_intraday",
            "schedule": crontab(hour=9, minute=45),
        },
        "check-market-status": {
            "task": "app.tasks.kill_switch_tasks.check_market_status",
            "schedule": 60.0,
        },
        "cleanup-expired-sessions": {
            "task": "app.tasks.kill_switch_tasks.cleanup_expired_sessions",
            "schedule": 3600.0,
        },
        "cleanup-idempotency-keys": {
            "task": "app.tasks.kill_switch_tasks.rotate_idempotency_keys",
            "schedule": 300.0,
        },
        "daily-trade-report": {
            # 16:00 IST → 10:30 UTC
            "task": "app.tasks.kill_switch_tasks.generate_daily_trade_report",
            "schedule": crontab(hour=10, minute=30),
        },
    }
    return app


celery_app = _build_celery()


__all__ = ["celery_app"]
