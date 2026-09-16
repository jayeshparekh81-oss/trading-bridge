"""The fill ingester — R2, replacing the hand-written leg SQL.

WHAT IT DOES
────────────
Reads fills from pine_replica's WS order-update tape (a file: zero Dhan REST
quota, which the live engine owns), decides each one's provenance, and writes
the verdict down ONCE.

TWO DESTINATIONS, AND THE SPLIT IS THE POINT
────────────────────────────────────────────
* ``broker_fill_provenance`` — EVERY fill, whatever it is. This is the audit of
  what the ACCOUNT did, not a customer surface. Manual and unidentified fills
  live here and nowhere else.
* the position's ``action_history`` — ONLY the bot's own broker-side exits, as
  "broker stop (auto)" legs. Manual and unknown fills are never written here,
  because this is the record shown to other people as the bot's.

WHY THE VERDICT IS STORED, NOT RECOMPUTED (founder's addition A)
───────────────────────────────────────────────────────────────
Provenance is decided from ``orderPlatform`` and ``algoOrdNo``, which exist only
in the tape — Dhan's trade book carries neither. Retention of the tape was
MEASURED on 2026-09-16 and there is none: no logrotate rule, no cron deletion,
no cleanup code. The files survive by luck. The day the box needs space, the
record since 1 Sep would lose the ability to say who placed what. So the answer
is written to the database at ingest and the page never reads the tape again.

IDEMPOTENT BY CONSTRUCTION
──────────────────────────
``broker_order_id`` is the PRIMARY KEY and writes are ``ON CONFLICT DO
NOTHING``. Running the ingester twice over the same tape adds nothing — not
"usually", but because the database refuses. The action_history append is
guarded the same way: a leg whose broker order id is already present is skipped.

ATTRIBUTION IS BY RECORDED ID, NEVER BY TIME
────────────────────────────────────────────
A stop child is attached to its position through: child fill -> ``algoOrdNo``
(Dhan's own field) -> parent Forever order -> the engine ledger that claims that
parent -> the trade's entry order id -> our entry leg's ``broker_order_id``.
Not one timestamp is compared anywhere in that chain.

READ-ONLY TOWARD pine_replica. This module only ever opens files under its log
directory. Nothing there is written, moved or rotated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.pnl_reconciler.order_tape import OrderProvenance

_logger = get_logger("domains.pnl_reconciler.ingest")

#: Dhan's ``orderPlatform`` for a hand-placed Dhan-app order — the ONLY value
#: that makes a fill manual under the founder's rule.
MANUAL_PLATFORM = "FAST"


@dataclass(frozen=True)
class IngestResult:
    """What one ingest run did, in numbers the operator can check."""

    seen: int = 0
    written: int = 0
    already_present: int = 0
    bot: int = 0
    manual: int = 0
    unknown: int = 0
    #: Fills that could not be identified. These ALERT — never silently filed.
    unknown_order_ids: tuple[str, ...] = ()
    #: True when the tape produced no records at all. Founder's addition B:
    #: this is ONE red, not a mass re-flagging of every fill.
    tape_empty: bool = False

    @property
    def clean(self) -> bool:
        return not self.tape_empty and not self.unknown_order_ids


def classify(
    order_id: str, prov: OrderProvenance | None, *, ledger_order_ids: set[str]
) -> str:
    """``bot`` | ``manual`` | ``unknown`` — the same three-way rule, one place.

    Order matters and is the founder's: a ledger claim BEATS the platform
    field, because pine_replica's stop children are FOVR and once its ledger
    claims one it is the bot's exit. Only ``FAST`` makes a fill manual.
    Everything else is ``unknown`` and must surface — filing an unclaimed FOVR
    as manual would blame a human for the bot's own fill.
    """
    if order_id in ledger_order_ids:
        return "bot"
    if prov is not None and prov.parent_order_id in ledger_order_ids:
        # A stop CHILD: its parent is claimed, so the child is the bot's.
        return "bot"
    if prov is not None and (prov.platform or "").upper() == MANUAL_PLATFORM:
        return "manual"
    return "unknown"


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None


async def ingest_fills(
    session: AsyncSession,
    fills: list[Any],
    tape: dict[str, OrderProvenance],
    *,
    ledger_order_ids: set[str],
    platform_order_ids: set[str] | None = None,
) -> IngestResult:
    """Record every fill's provenance exactly once. Returns what happened.

    ``ledger_order_ids`` — every order id pine_replica's own ledger claims,
    PLUS the parent Forever ids. ``platform_order_ids`` — order ids this
    platform placed (from ``strategy_executions``); they are the bot's by
    definition and do not need the tape at all.

    🔴 ADDITION B. A tape that loads EMPTY is one red, not a verdict on every
    fill. The last time the tape silently loaded empty (a glob expanded on the
    wrong side of a container boundary) every non-bot fill would have been
    re-labelled "pehchaan nahi" at once — a page full of alarm caused by a
    mount, not by the account. So the run stops, reports, and classifies
    nothing.
    """
    if fills and not tape:
        _logger.error("ingest.tape_empty", fills=len(fills))
        return IngestResult(seen=len(fills), tape_empty=True)

    known_platform = platform_order_ids or set()
    all_claimed = set(ledger_order_ids) | known_platform

    result = IngestResult()
    written = already = bot = manual = unknown = 0
    unknown_ids: list[str] = []

    for fill in fills:
        order_id = str(getattr(fill, "order_id", "") or "")
        if not order_id:
            continue
        prov = tape.get(order_id)
        verdict = classify(order_id, prov, ledger_order_ids=all_claimed)
        if verdict == "bot":
            bot += 1
        elif verdict == "manual":
            manual += 1
        else:
            unknown += 1
            unknown_ids.append(order_id)

        row = await session.execute(
            text(
                """
                INSERT INTO broker_fill_provenance (
                    broker_order_id, security_id, symbol, side, quantity, price,
                    filled_at, order_platform, provenance, parent_order_id,
                    correlation_id, billed_charges
                ) VALUES (
                    :oid, :sec, :sym, :side, :qty, :price,
                    :filled_at, :platform, :provenance, :parent,
                    :corr, :charges
                )
                ON CONFLICT (broker_order_id) DO NOTHING
                RETURNING broker_order_id
                """
            ),
            {
                "oid": order_id,
                "sec": str(getattr(fill, "contract", "") or ""),
                "sym": getattr(fill, "symbol", None),
                "side": str(getattr(fill, "side", "") or "").upper(),
                "qty": int(getattr(fill, "qty", 0) or 0),
                "price": _as_decimal(getattr(fill, "price", None)),
                "filled_at": _parse_ts(getattr(fill, "ts", None)),
                "platform": (prov.platform if prov else None),
                "provenance": verdict,
                "parent": (prov.parent_order_id if prov else None),
                "corr": (prov.correlation_id if prov else None),
                "charges": _as_decimal(getattr(fill, "charges", None)),
            },
        )
        if row.first() is None:
            already += 1
        else:
            written += 1

    result = IngestResult(
        seen=len(fills),
        written=written,
        already_present=already,
        bot=bot,
        manual=manual,
        unknown=unknown,
        unknown_order_ids=tuple(unknown_ids),
    )
    _logger.info(
        "ingest.done",
        seen=result.seen,
        written=result.written,
        already=result.already_present,
        bot=bot,
        manual=manual,
        unknown=unknown,
    )
    if unknown_ids:
        # Never silently filed. The 15:50 check turns this into a Telegram line.
        _logger.error("ingest.unidentified_fills", order_ids=unknown_ids[:20])
    return result


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return None


async def stored_provenance(session: AsyncSession, order_id: str) -> dict[str, Any] | None:
    """What was decided about this fill at ingest, read back from the DB.

    The whole point of addition A: this answers without the tape existing.
    """
    row = (
        await session.execute(
            text(
                "SELECT broker_order_id, order_platform, provenance, parent_order_id, "
                "billed_charges FROM broker_fill_provenance WHERE broker_order_id = :oid"
            ),
            {"oid": order_id},
        )
    ).mappings().first()
    return dict(row) if row is not None else None


__all__ = [
    "MANUAL_PLATFORM",
    "IngestResult",
    "classify",
    "ingest_fills",
    "stored_provenance",
]
