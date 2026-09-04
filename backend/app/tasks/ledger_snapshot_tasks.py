"""Transparency Ledger — scheduled daily snapshot (DISABLED by default).

Beat runs :func:`take_daily_snapshots` at 16:15 IST on weekdays. It is a
thin sync wrapper (Celery prefork) around :func:`create_daily_snapshot`
for every PUBLISHED listing, with three hard rules:

* **Dormant unless ``LEDGER_DAILY_SNAPSHOT_ENABLED`` is true** — returns
  ``{"status": "dormant"}`` and inserts nothing. The founder takes the FIRST
  snapshot of each chain by hand (sequence #1 is a human decision on an
  append-only record); the beat only continues an existing chain.
* **Never a zero.** ``NothingToPublishError`` (no priced round trip / no
  completed paper session) is logged and skipped — no row.
* **Idempotent per UTC day.** ``SnapshotAlreadyExistsError`` (manual +
  beat overlap) is logged and skipped.

Touches no strategy, position, order or broker path. Reads the reconciler
in read-only mode; writes only ``ledger_snapshots`` + ``ledger_attestations``.
"""

from __future__ import annotations

from typing import Any

from celery import shared_task
from sqlalchemy import select

from app.core.async_bridge import run_async as _run
from app.core.logging import get_logger

logger = get_logger("app.tasks.ledger_snapshot")


@shared_task(name="app.tasks.ledger_snapshot_tasks.take_daily_snapshots")  # type: ignore[untyped-decorator]
def take_daily_snapshots() -> dict[str, Any]:
    """Snapshot every published listing once for today (gated, see module doc)."""

    async def _go() -> dict[str, Any]:
        from app.core.config import get_settings
        from app.db.models.marketplace_listing import MarketplaceListing
        from app.db.session import get_sessionmaker
        from app.strategy_engine.ledger.snapshots import (
            NothingToPublishError,
            SnapshotAlreadyExistsError,
            create_daily_snapshot,
        )

        settings = get_settings()
        if not settings.ledger_daily_snapshot_enabled:
            logger.info(
                "ledger_snapshot.dormant", extra={"reason": "LEDGER_DAILY_SNAPSHOT_ENABLED=false"}
            )
            return {"status": "dormant", "listings": 0, "created": 0, "skipped": 0}

        maker = get_sessionmaker()
        created = 0
        skipped = 0
        listing_ids: list[Any] = []
        async with maker() as session:
            listing_ids = list(
                (
                    await session.execute(
                        select(MarketplaceListing.id).where(
                            MarketplaceListing.status == "published"
                        )
                    )
                ).scalars()
            )
        for listing_id in listing_ids:
            async with maker() as session:
                try:
                    snap = await create_daily_snapshot(session, listing_id)
                except SnapshotAlreadyExistsError:
                    skipped += 1
                    logger.info(
                        "ledger_snapshot.skip_duplicate_day", extra={"listing_id": str(listing_id)}
                    )
                except NothingToPublishError as exc:
                    skipped += 1
                    logger.info(
                        "ledger_snapshot.skip_nothing_to_publish",
                        extra={"listing_id": str(listing_id), "reason": str(exc)},
                    )
                except Exception:
                    skipped += 1
                    logger.exception(
                        "ledger_snapshot.listing_failed", extra={"listing_id": str(listing_id)}
                    )
                else:
                    created += 1
                    logger.info(
                        "ledger_snapshot.created",
                        extra={
                            "listing_id": str(listing_id),
                            "sequence": snap.sequence_number,
                            "live_trades": snap.live_trades_count,
                            "unpriced": snap.unpriced_positions,
                            "pnl_basis": snap.pnl_basis,
                        },
                    )
        summary = {
            "status": "ran",
            "listings": len(listing_ids),
            "created": created,
            "skipped": skipped,
        }
        logger.info("ledger_snapshot.scan", extra=summary)
        return summary

    outcome: dict[str, Any] = _run(_go())
    return outcome
