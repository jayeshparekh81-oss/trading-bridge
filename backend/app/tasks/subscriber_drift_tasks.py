"""Scheduled subscriber drift pass — the composition point.

This is the only place that assembles the three built-but-unwired pieces:

    make_subscriber_position_fetcher   (reads ONE subscriber's broker positions)
        -> run_subscriber_drift_pass   (batches, compares, flips AUTO->MANUAL)
            -> check_and_flip_subscription

It places NO order. It cannot: nothing in this import graph reaches
``place_order``, an order router, or a broker WRITE call, and a test asserts
that. The only mutation it can make is one subscription's ``execution_mode``,
AUTO -> MANUAL, one way. The customer re-enables it themselves.

WIRED, NOT ENABLED. The flag is checked HERE, before any query, and again
inside the pass. ``subscriber_drift_enabled`` defaults False, so scheduling
this makes the machinery REACHABLE and turns nothing on.

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

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from celery import shared_task

from app.core.async_bridge import run_async as _run
from app.core.logging import get_logger

logger = get_logger("app.tasks.subscriber_drift")


@dataclass(frozen=True)
class _SubscriberRef:
    """The three fields ``make_subscriber_position_fetcher`` duck-types on.

    The fetcher is deliberately import-free of the fan-out, so it takes any
    object carrying these. The drift pass works in ``MarketplaceSubscription``
    rows, whose primary key is ``id`` rather than ``subscription_id`` — this
    adapter is that one-field rename, in one place.
    """

    subscription_id: UUID
    subscriber_id: UUID
    broker_credential_id: UUID | None


@shared_task(name="app.tasks.subscriber_drift_tasks.run_drift_pass")  # type: ignore[untyped-decorator]
def run_drift_pass() -> dict[str, Any]:
    """One subscriber drift pass. Dormant unless the flag is on."""

    async def _go() -> dict[str, Any]:
        from app.core.config import get_settings
        from app.db.session import get_sessionmaker
        from app.services.subscriber_broker_positions import (
            make_subscriber_position_fetcher,
        )
        from app.workers.subscriber_drift_pass import (
            _candidates,
            run_subscriber_drift_pass,
        )

        # FLAG FIRST, before any query. The pass checks it too, but it is
        # checked here as well so a dormant tick costs exactly one settings
        # read — no DB round-trip, no session, no broker contact.
        if not get_settings().subscriber_drift_enabled:
            logger.debug("subscriber_drift_task.dormant")
            return {"dormant": True, "checked": 0, "flipped": 0, "unknown": 0}

        maker = get_sessionmaker()
        async with maker() as session:
            # The fetcher must be built from the SAME candidate set the pass
            # will examine: it memoises per credential and refuses any
            # subscription it was not given ("unknown subscription"), which is
            # the safe default but would make every fetch fail if the two
            # disagreed. So the candidates are resolved once, here, and used
            # for both.
            rows = await _candidates(session)
            subscribers = [
                _SubscriberRef(
                    subscription_id=sub.id,
                    subscriber_id=sub.subscriber_id,
                    broker_credential_id=getattr(sub, "broker_credential_id", None),
                )
                for sub, _pos in rows
            ]

            # The fetcher is built HERE and injected, so the worker never
            # constructs a broker itself. Every failure inside it RAISES, which
            # the batch layer converts to POSITION_UNKNOWN — and unknown is
            # never treated as drift.
            fetch = make_subscriber_position_fetcher(session, subscribers)
            report = await run_subscriber_drift_pass(
                session, fetch_broker_positions=fetch
            )

        out = {
            "dormant": report.dormant,
            "checked": report.checked,
            "flipped": report.flipped,
            "unknown": report.unknown,
        }
        logger.info("subscriber_drift_task.done", **out)
        return out

    # run_async, NOT asyncio.run: a fresh event loop per task orphans the
    # lru_cached engine/Redis singletons bound to the previous one (the
    # documented Celery loop bug). async_bridge reuses the per-process loop.
    result: dict[str, Any] = _run(_go())
    return result


__all__ = ["run_drift_pass"]
