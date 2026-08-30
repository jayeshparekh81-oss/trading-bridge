"""Scheduled subscriber drift pass — the composition point.

This is the only place that assembles the three built-but-unwired pieces:

    make_subscriber_position_fetcher   (reads ONE subscriber's broker positions)
        -> run_subscriber_drift_pass   (batches, compares, flips AUTO->MANUAL)
            -> check_and_flip_subscription

It places NO order. It cannot: nothing in this import graph reaches
``place_order``, an order router, or a broker WRITE call, and a test asserts
that. The only mutation it can make is one subscription's ``execution_mode``,
AUTO -> MANUAL, one way. The customer re-enables it themselves.

WIRED, NOT ENABLED. ``run_subscriber_drift_pass`` returns ``dormant`` unless
``subscriber_drift_enabled`` is true, and that flag defaults False. Scheduling
this makes the machinery REACHABLE; it turns nothing on.

CADENCE — every 5 minutes, market hours only, Mon-Fri (UTC 03:00-10:59 covers
IST 08:30-16:29, i.e. pre-open through post-close settle).

  * Drift is only detectable, and only MATTERS, while the market is open: that
    is the only window in which anyone can close a position, and the only
    window in which the system might act on one that is already gone.
  * 5 minutes bounds the staleness window to well under one 15m bar. Acting on
    a position the customer already closed is worse than the pnl-reconciler's
    failure mode (a late P&L row), which is why this runs 3x tighter than that
    job's 15 minutes.
  * Not 1 minute: each pass costs one broker read per subscriber holding an
    open position, against that subscriber's own Dhan rate limit. ~75 passes
    per session is modest; ~375 would not be.
  * Silent outside market hours — no broker calls, no token pressure, and
    nothing to find.
"""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from app.core.logging import get_logger

logger = get_logger("app.tasks.subscriber_drift")


@shared_task(name="app.tasks.subscriber_drift_tasks.run_drift_pass")  # type: ignore[untyped-decorator]
def run_drift_pass() -> dict[str, Any]:
    """One subscriber drift pass. Dormant unless the flag is on."""

    async def _go() -> dict[str, Any]:
        from app.db.session import get_sessionmaker
        from app.services.subscriber_broker_positions import (
            make_subscriber_position_fetcher,
        )
        from app.workers.subscriber_drift_pass import run_subscriber_drift_pass

        maker = get_sessionmaker()
        async with maker() as session:
            # The fetcher is built HERE and injected, so the worker itself
            # never constructs a broker. Every failure inside it RAISES, which
            # the batch layer converts to POSITION_UNKNOWN — and unknown is
            # never treated as drift.
            fetch = make_subscriber_position_fetcher(session)
            report = await run_subscriber_drift_pass(
                session, fetch_broker_positions=fetch
            )

        out = {
            "dormant": report.dormant,
            "checked": report.checked,
            "flipped": report.flipped,
            "unknown": report.unknown,
        }
        if report.dormant:
            logger.debug("subscriber_drift_task.dormant")
        else:
            logger.info("subscriber_drift_task.done", **out)
        return out

    return asyncio.run(_go())


__all__ = ["run_drift_pass"]
