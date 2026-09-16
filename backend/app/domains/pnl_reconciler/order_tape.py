"""The WS order-update tape: where ``orderPlatform`` actually comes from.

WHY THIS EXISTS (2026-09-16, measured)
──────────────────────────────────────
The founder's rule turns on Dhan's ``orderPlatform``: ``FAST`` is a Dhan-app
order placed by hand, and only a FAST fill between a position's entry and its
close makes that position "manual se band".

Dhan's TRADE BOOK does not carry that field. Its full key set, measured from a
real pull of 318 rows, is::

    brokerageCharges createTime customSymbol dhanClientId drvExpiryDate
    drvOptionType drvStrikePrice exchangeOrderId exchangeSegment exchangeTime
    exchangeTradeId exchangeTransactionCharges instrument isin orderId
    orderType productType sebiTax securityId serviceTax stampDuty stt
    tradedPrice tradedQuantity tradingSymbol transactionType updateTime

No ``orderPlatform``, no ``correlationId``, no ``algoOrdNo``.

The WS order-update tape carries all three. So provenance is joined in from the
tape on ``orderId`` — a file read, costing zero Dhan quota, which is what the
founder's rule requires (the live engine owns the REST budget).

WHAT A GAP MEANS
────────────────
A fill whose order id the tape does not know is NOT assumed manual and NOT
assumed the bot's. It has no platform, so :meth:`AccountFill.provenance`
answers ``unknown``, the position is tagged "pehchaan nahi" and its P&L stays
NULL — and :func:`coverage_gaps` reports the gap so the 15:50 truth check can
send MISMATCH naming it. Founder's ruling: never silently file an unknown as
manual.

Measured coverage at build time: the tape begins 2026-09-02. 155 account fills
on BSE futures predate it (2026-05-04 .. 2026-08-31) — every one of them
BEFORE 2026-09-01, so none is inside the record. Every in-record fill has a
tape entry.

READ-ONLY. This module only ever opens files under pine_replica's log
directory. It never writes there, and nothing in pine_replica is touched.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Where the engine writes one JSON line per Dhan order-update frame.
DEFAULT_TAPE_GLOB = "order_updates_*.jsonl"


@dataclass(frozen=True)
class OrderProvenance:
    """What the tape knows about one broker order."""

    order_id: str
    #: Dhan's ``orderPlatform``: API | FOVR | FAST | …
    platform: str | None
    #: Dhan's ``algoOrdNo`` — the PARENT Forever order for a stop child. This
    #: is the hop that attributes an engine stop to its position without ever
    #: comparing timestamps.
    parent_order_id: str | None
    correlation_id: str | None


def _frames(path: Path) -> Iterator[dict[str, Any]]:
    try:
        handle = path.open()
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                outer = json.loads(line)
                yield json.loads(outer["raw"])["Data"]
            except (ValueError, KeyError, TypeError):
                continue


def load_tape(*paths: str | Path) -> dict[str, OrderProvenance]:
    """``{order_id: OrderProvenance}`` from one or more tape files.

    Later frames win: an order's last frame is its settled state, and the
    fields this reads (platform, parent, correlation) do not change across an
    order's life anyway.
    """
    out: dict[str, OrderProvenance] = {}
    for p in paths:
        for data in _frames(Path(p)):
            order_id = str(data.get("orderNo") or "").strip()
            if not order_id:
                continue
            parent = data.get("algoOrdNo")
            out[order_id] = OrderProvenance(
                order_id=order_id,
                platform=(str(data.get("orderPlatform")).strip().upper() or None)
                if data.get("orderPlatform") is not None
                else None,
                parent_order_id=str(parent) if parent not in (None, "", 0, "0") else None,
                correlation_id=(
                    str(data.get("correlationId")).strip()
                    if data.get("correlationId") is not None
                    else None
                ),
            )
    return out


def tape_files(directory: str | Path, pattern: str = DEFAULT_TAPE_GLOB) -> list[Path]:
    """Every tape file in ``directory``, oldest first. Empty when unreadable."""
    try:
        return sorted(Path(directory).glob(pattern))
    except OSError:
        return []


def coverage_gaps(
    fills: Iterable[Any], tape: dict[str, OrderProvenance], *, since: str | None = None
) -> list[str]:
    """Human-readable gaps, or ``[]`` when the tape covers every fill.

    🔴 A GAP IS A RED, NOT A SHRUG (founder's ruling 2026-09-16(b)). The 15:50
    truth check turns a non-empty return into MISMATCH with the gap named, and
    the affected fills stay "pehchaan nahi" on the page. Reporting nothing here
    when the tape is short would leave a fill silently mis-attributed, which is
    the failure this whole module exists to prevent.

    ``since`` (``YYYY-MM-DD``) scopes the check to the record, so the 155
    known pre-tape fills of the archive do not raise a gap every single day.
    """
    gaps: list[str] = []
    for fill in fills:
        ts = str(getattr(fill, "ts", "") or "")
        if since is not None and ts[:10] < since:
            continue
        order_id = str(getattr(fill, "order_id", "") or "")
        if not order_id:
            gaps.append("a fill carries no order id, so it cannot be identified at all")
            continue
        if order_id not in tape:
            gaps.append(
                f"order {order_id} ({ts[:19] or 'no time'}) has no WS order-update "
                "record, so its platform is unknown"
            )
    return gaps


def apply_provenance(fills: Iterable[Any], tape: dict[str, OrderProvenance]) -> list[Any]:
    """Return the fills with ``order_platform`` filled in from the tape.

    A fill the tape does not know is returned UNCHANGED, keeping
    ``order_platform=None`` — which reads as ``unknown``, never as manual.
    """
    from dataclasses import replace

    out = []
    for fill in fills:
        known = tape.get(str(getattr(fill, "order_id", "") or ""))
        out.append(fill if known is None else replace(fill, order_platform=known.platform))
    return out


__all__ = [
    "DEFAULT_TAPE_GLOB",
    "OrderProvenance",
    "apply_provenance",
    "coverage_gaps",
    "load_tape",
    "tape_files",
]
