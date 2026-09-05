"""Celery tasks for the customer lane.

REGISTERED BUT DISARMED. ``register_beat_entries`` only installs schedules when
``CUSTOMER_LANE_BEAT_ENABLED`` is true, which defaults FALSE. Each task ALSO
re-checks ``ladder_enabled`` at execution time, so a schedule that somehow fired
still does nothing.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from celery.schedules import crontab

from app.db.models.customer_lane import LadderStep
from app.domains.customer_lane import config as lane_config

IST = timezone(timedelta(hours=5, minutes=30))

#: beat entry name -> (task, LadderStep, config attribute holding the IST time)
LADDER_BEAT: dict[str, tuple[str, LadderStep, str]] = {
    "customer-lane-r1": ("app.tasks.customer_lane_tasks.run_r1", LadderStep.R1, "r1_at"),
    "customer-lane-r2": ("app.tasks.customer_lane_tasks.run_r2", LadderStep.R2, "r2_at"),
    "customer-lane-call": ("app.tasks.customer_lane_tasks.run_call", LadderStep.CALL, "call_at"),
    "customer-lane-red": ("app.tasks.customer_lane_tasks.run_red", LadderStep.RED, "red_at"),
}


def today_ist() -> date:
    return datetime.now(IST).date()


def register_beat_entries(app) -> dict:
    """Install the ladder schedules ONLY when the beat flag is on. Returns what was
    installed (empty dict when disarmed) so a test can assert the disarmed state."""
    cfg = lane_config.load()
    if not cfg.beat_enabled:
        return {}

    # ARM-TIME GATE. A lane that cannot answer "is today a trading day?" must not
    # be scheduled at all. Raising here means a bad deploy fails at startup, by
    # name, instead of failing silently every morning at 07:45.
    from app.domains.customer_lane.preflight import assert_can_arm
    assert_can_arm()
    entries = {}
    for name, (task, _step, attr) in LADDER_BEAT.items():
        t = getattr(cfg, attr)
        # beat runs in UTC on this box; convert the configured IST time
        utc = (datetime(2000, 1, 1, t.hour, t.minute, tzinfo=IST)
               .astimezone(timezone.utc))
        entries[name] = {"task": task,
                         "schedule": crontab(hour=utc.hour, minute=utc.minute,
                                             day_of_week="1-5")}
    app.conf.beat_schedule.update(entries)
    return entries


async def _run(step: LadderStep) -> list:
    """Shared body. Re-reads config so a long-lived worker cannot cache a stale flag."""
    cfg = lane_config.load()
    if not cfg.ladder_enabled:
        return []
    from app.db.session import get_sessionmaker  # local import: keep beat import light
    from app.domains.customer_lane.ladder import run_step
    maker = get_sessionmaker()
    async with maker() as session:
        out = await run_step(session, step, trading_date=today_ist())
        await session.commit()
        return out


__all__ = ["register_beat_entries", "LADDER_BEAT", "today_ist", "IST"]
