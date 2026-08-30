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
from celery.signals import worker_process_init

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
            "app.tasks.notification_tasks",
            # Day-2 of the backtest extension sprint. Worker auto-discovers
            # @shared_task definitions from this module. Until founder
            # mounts the FastAPI router (Day 3 deliverable, NOT done on this
            # branch), the task is unreachable from the public API — but
            # registration is required so the worker can resolve the task
            # name at apply_async() call time during tests + future PRs.
            "app.backtest_extension.celery_tasks",
            "app.tasks.signal_execution",
            "app.tasks.historical_backfill_tasks",
            "app.tasks.pnl_reconciler_tasks",
            "app.tasks.scrip_master_tasks",
            "app.tasks.options_expiry_tasks",
            "app.tasks.subscriber_drift_tasks",
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
        "daily-summary-notification": {
            # 16:00 IST → 10:30 UTC
            "task": "app.tasks.notification_tasks.send_daily_summary_all",
            "schedule": crontab(hour=10, minute=30),
        },
        "weekly-report-notification": {
            # Sunday 18:00 IST → 12:30 UTC
            "task": "app.tasks.notification_tasks.send_weekly_report_all",
            "schedule": crontab(hour=12, minute=30, day_of_week=0),
        },
        "pnl-reconciler-intraday": {
            # Every 15 min during market hours: IST 08:30-15:29 -> UTC 03:00-09:59,
            # Mon-Fri. Going-forward P&L recording; log-only until
            # PNL_RECONCILER_WRITE is flipped on.
            "task": "app.tasks.pnl_reconciler_tasks.reconcile_recent_pnl",
            "schedule": crontab(minute="*/15", hour="3-9", day_of_week="1-5"),
        },
        "subscriber-drift-pass": {
            # Every 5 min, market hours only: IST 08:30-16:29 -> UTC 03:00-10:59,
            # Mon-Fri. WIRED, NOT ENABLED — the pass returns `dormant` unless
            # SUBSCRIBER_DRIFT_ENABLED is true (default False), so this schedule
            # makes the machinery reachable and turns nothing on.
            #
            # 5 min (vs the reconciler's 15) because the failure it prevents is
            # worse: acting on a position the customer already closed, rather
            # than recording a P&L row late. It bounds staleness to well under
            # one 15m bar. Not 1 min — each pass costs one broker READ per
            # subscriber holding an open position, against that subscriber's
            # own rate limit.
            "task": "app.tasks.subscriber_drift_tasks.run_drift_pass",
            "schedule": crontab(minute="*/5", hour="3-10", day_of_week="1-5"),
        },
        "pnl-reconciler-eod": {
            # Once after market close: 16:00 IST -> 10:30 UTC, Mon-Fri; catches
            # the day's late closes after the intraday window ends.
            "task": "app.tasks.pnl_reconciler_tasks.reconcile_recent_pnl",
            "schedule": crontab(minute=30, hour=10, day_of_week="1-5"),
        },
        "scrip-master-warm-premarket": {
            # 09:05 IST → 03:35 UTC daily — refresh the worker's scrip-master
            # before market open so the day's first F&O signal never pays the
            # ~9s CSV download inside the order path (2026-07-06 CDSL incident).
            "task": "app.tasks.scrip_master_tasks.warm_scrip_master",
            "schedule": crontab(hour=3, minute=35),
        },
        "scrip-master-warm-periodic": {
            # Every 6h — keeps the 24h TTL from expiring between sessions.
            # No-op when the cache is still fresh.
            "task": "app.tasks.scrip_master_tasks.warm_scrip_master",
            "schedule": 21600.0,
        },
        "options-expiry-sweep": {
            # 15:35 IST → 10:05 UTC Mon-Fri — right after the 15:30 IST
            # expiry-day square-off cutoff, while the scrip master still lists
            # the expiring contract (delisting happens on a later refresh — the
            # BSE-MAY2026 lesson; after delisting the sweep's symbol-parse
            # fallback still covers dated leg symbols). Idempotent, and
            # DORMANT: the sweep gates on options_execution_enabled (default
            # False) and returns without touching a row.
            "task": "app.tasks.options_expiry_tasks.sweep_expired_option_positions",
            "schedule": crontab(minute=5, hour=10, day_of_week="1-5"),
        },
    }
    return app


celery_app = _build_celery()


@worker_process_init.connect
def _warm_scrip_master_on_fork(**_kwargs: object) -> None:
    """Schedule a scrip-master warm in every prefork child at startup.

    The cache (`app.brokers.dhan._SCRIP_MASTER`) is module-level, so each
    forked child starts cold — a beat-scheduled warm only reaches whichever
    child picks the task up. Scheduling here covers all children.

    Deliberately NON-blocking: Celery kills a child whose init handlers
    block >4s, and the EC2→Dhan CDN download alone takes ~8s. So the warm
    is created as a pending task on the child's persistent loop (the one
    ``run_async`` drives — see async_bridge); it executes interleaved with
    the child's first task, typically a 60s-cadence beat task, so the child
    is warm within a minute or two of boot. An F&O signal that lands before
    then simply joins the in-flight download via the cache's lock — worst
    case equals today's on-demand load, never worse. The lock binds to the
    persistent loop either way, keeping the 2026-05-24 loop incident dead.
    """
    try:
        from app.core.async_bridge import _get_persistent_loop
        from app.tasks.scrip_master_tasks import warm

        loop = _get_persistent_loop()
        task = loop.create_task(warm())

        def _log_failure(done: object) -> None:
            exc = done.exception() if not done.cancelled() else None  # type: ignore[attr-defined]
            if exc is not None:
                from app.core.logging import get_logger

                get_logger("app.tasks.celery_app").warning(
                    "worker.scrip_master.warm_failed", error=str(exc)
                )

        task.add_done_callback(_log_failure)
    except Exception as exc:
        from app.core.logging import get_logger

        get_logger("app.tasks.celery_app").warning(
            "worker.scrip_master.warm_failed", error=str(exc)
        )


__all__ = ["celery_app"]
