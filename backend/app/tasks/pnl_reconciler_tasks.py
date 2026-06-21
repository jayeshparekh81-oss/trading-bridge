"""Scheduled P&L reconciler task — going-forward recording.

A thin sync wrapper (Celery prefork) around the standalone reconciler domain
:mod:`app.domains.pnl_reconciler`. Beat runs it every ~15 min during market
hours plus once after close. It scans recently-CLOSED positions whose
``final_pnl`` is still NULL, computes realized P&L from the REAL broker fills,
and:

* **LOG-ONLY by default** (``PNL_RECONCILER_WRITE`` False) — logs what it WOULD
  record, writes nothing;
* with the flag on — annotates ``final_pnl`` on FULLY-reconciled trips only.

Going-forward only: the ``PNL_RECONCILER_LOOKBACK_HOURS`` window excludes
historical / manual-era positions. Incomplete trips are flagged + skipped,
never guessed.

This task does NOT touch the live order/close path — it imports none of the
sacred execution modules (executor / direct_exit / brokers / webhook). Like
the other tasks here it is a thin sync shim around an async coroutine run on
the shared worker loop (``app.core.async_bridge.run_async``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task

from app.core.async_bridge import run_async as _run
from app.core.logging import get_logger

logger = get_logger("app.tasks.pnl_reconciler")


@shared_task(name="app.tasks.pnl_reconciler_tasks.reconcile_recent_pnl")  # type: ignore[untyped-decorator]
def reconcile_recent_pnl() -> dict[str, Any]:
    """Reconcile realized P&L for recently-closed positions (log-only default)."""

    async def _go() -> dict[str, Any]:
        from app.core.config import get_settings
        from app.db.session import get_sessionmaker
        from app.domains.pnl_reconciler import reconcile_unrecorded

        settings = get_settings()
        write = bool(settings.pnl_reconciler_write)
        lookback_hours = int(settings.pnl_reconciler_lookback_hours)
        since = datetime.now(UTC) - timedelta(hours=lookback_hours)

        maker = get_sessionmaker()
        async with maker() as session:
            result = await reconcile_unrecorded(session, since=since, write=write)

        # Per-trip observability — complete trips carry the computed P&L; in
        # log-only mode these are the "would record" lines. final_pnl receives
        # NET (gross minus estimated costs) when write is enabled.
        for trip in result.complete_trips:
            costs_total = str(trip.costs.total) if trip.costs is not None else None
            logger.info(
                "pnl_reconciler.complete_trip",
                extra={
                    "action": "recorded" if write else "would_record",
                    "position_id": str(trip.position_id),
                    "symbol": trip.symbol,
                    "direction": trip.direction,
                    "qty": trip.position_qty,
                    "gross_pnl": str(trip.gross_pnl),
                    "costs_total": costs_total,
                    "costs_estimated": trip.costs.estimated if trip.costs else None,
                    "net_pnl": str(trip.net_pnl),
                    "write_enabled": write,
                },
            )
        for trip in result.incomplete_trips:
            logger.info(
                "pnl_reconciler.skip_incomplete",
                extra={
                    "position_id": str(trip.position_id),
                    "symbol": trip.symbol,
                    "flags": trip.flags,
                },
            )

        summary: dict[str, Any] = {
            "candidates": len(result.trips),
            "complete": len(result.complete_trips),
            "incomplete": len(result.incomplete_trips),
            "write_enabled": write,
            "annotated": result.annotated,
            "lookback_hours": lookback_hours,
            "gross_realized": str(result.gross_realized),
            "total_costs_estimated": str(result.total_costs),
            "net_realized": str(result.net_realized),
        }
        logger.info("pnl_reconciler.scan", extra=summary)
        return summary

    # ``run_async`` is typed ``-> Any``; bind to a typed name so the task's
    # declared return type is preserved.
    outcome: dict[str, Any] = _run(_go())
    return outcome
