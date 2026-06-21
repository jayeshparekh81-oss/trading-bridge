"""Post-hoc P&L reconciliation logic.

Why this exists
---------------
The live execution path never computes ``strategy_positions.final_pnl`` (see
the P&L-gap audit): positions open and close correctly but the field is left
NULL, the ``trades`` table is unused, and ``trade_markers`` is never written
for live/paper strategies. Meanwhile the REAL broker fills *are* captured — in
``strategy_executions.broker_response`` — they were just never promoted to a
structured P&L.

This module reconstructs realized P&L after the fact:

1. Read a strategy's CLOSED ``strategy_positions`` + all its
   ``strategy_executions`` (joined via ``strategy_signals``).
2. Parse the REAL fill (price / qty / status) out of each execution's
   ``broker_response`` — Dhan ``raw.{orderStatus,price,filledQty}`` for live,
   the paper-sim ``avg_price`` / ``fill_price`` shapes for paper. NEVER the
   TradingView payload price (which ``position.avg_entry_price`` stored).
3. Match entry ↔ partial/exit/SL legs using each position's
   ``action_history`` (an exact ``signal_id`` chain — no time-windowing).
4. Compute realized P&L per round trip from the real fills.
5. Optionally annotate ``final_pnl`` on the matched CLOSED position.

Safety
------
This is a SEPARATE job. It does not import or touch the sacred execution path
(``strategy_executor`` / ``direct_exit`` / ``brokers`` / ``webhook``). In the
default dry-run it writes nothing; in write mode it only assigns ``final_pnl``
on already-CLOSED positions whose round trip reconciles COMPLETELY. Incomplete
trips (e.g. an exit done manually on the broker, absent from the DB) are
flagged and left untouched — never guessed.

P&L is GROSS. Costs (brokerage / STT / exchange / GST / stamp) are not yet
modelled — see ``# TODO(costs)``.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.domains.pnl_reconciler.costs import (
    DEFAULT_SEGMENT,
    CostBreakdown,
    compute_costs,
)

_logger = get_logger("domains.pnl_reconciler")

# Terminal "filled" markers across live (Dhan) + paper-sim responses.
_FILLED_STATUSES = frozenset({"TRADED", "COMPLETE", "COMPLETED", "FILLED", "EXECUTED"})
_PENDING_STATUSES = frozenset({"TRANSIT", "PENDING", "OPEN", "MODIFIED"})

# TWO_DP / display quantum.
_Q2 = Decimal("0.01")


# ─── Value objects ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class FillInfo:
    """The REAL fill parsed out of one execution's ``broker_response``."""

    status: str  # normalized: FILLED | PENDING | OTHER
    raw_status: str | None  # original e.g. "TRADED" / "TRANSIT" / "complete"
    price: Decimal | None
    qty: int | None
    source: str  # dhan | paper_entry | paper_exit | unknown


@dataclass
class ExitLeg:
    """One close leg (partial / exit / SL) of a round trip."""

    leg_role: str
    qty: int
    price: Decimal | None
    status: str
    signal_id: uuid.UUID | None
    realized_pnl: Decimal | None  # gross; None when the leg cannot be priced


@dataclass
class RoundTrip:
    """A reconciled round trip mapped to one CLOSED position."""

    position_id: uuid.UUID | None
    symbol: str
    direction: str  # long | short | unknown
    position_qty: int
    entry_legs: int  # number of FILLED entry orders (flat brokerage is per order)
    entry_price: Decimal | None  # qty-weighted real entry fill
    exits: list[ExitLeg]
    exit_qty_total: int
    gross_pnl: Decimal | None  # real-fill P&L BEFORE costs; None unless complete
    costs: CostBreakdown | None  # estimated Indian F&O charges; None unless complete
    net_pnl: Decimal | None  # gross_pnl - costs.total; None unless complete
    complete: bool
    flags: list[str]


@dataclass
class ReconcileResult:
    """Outcome of a reconciliation run.

    ``strategy_id`` is set for a single-strategy run and ``None`` for the
    going-forward recent-scan (which can span strategies).
    """

    strategy_id: uuid.UUID | None
    trips: list[RoundTrip]
    annotated: int  # positions whose final_pnl was written (write mode only)
    wrote: bool

    @property
    def complete_trips(self) -> list[RoundTrip]:
        return [t for t in self.trips if t.complete]

    @property
    def incomplete_trips(self) -> list[RoundTrip]:
        return [t for t in self.trips if not t.complete]

    @property
    def gross_realized(self) -> Decimal:
        return sum(
            (t.gross_pnl for t in self.trips if t.gross_pnl is not None),
            Decimal(0),
        )

    @property
    def total_costs(self) -> Decimal:
        return sum(
            (t.costs.total for t in self.trips if t.costs is not None),
            Decimal(0),
        )

    @property
    def net_realized(self) -> Decimal:
        return sum(
            (t.net_pnl for t in self.trips if t.net_pnl is not None),
            Decimal(0),
        )


# ─── Parsing helpers ───────────────────────────────────────────────────


def _to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    return None


def _to_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    dec = _to_decimal(value)
    return int(dec) if dec is not None else None


def _to_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _normalize_status(raw: object) -> str:
    text = str(raw or "").strip().upper()
    if text in _FILLED_STATUSES:
        return "FILLED"
    if text in _PENDING_STATUSES:
        return "PENDING"
    return "OTHER"


def parse_fill(broker_response: dict[str, Any] | None) -> FillInfo | None:
    """Extract the REAL fill from a ``broker_response`` of any known shape.

    Three shapes are produced by the writers we read:

    * **Dhan (live)** — ``{"raw": {"orderStatus","price","filledQty",...}, ...}``
    * **paper entry** (``strategy_executor._simulate_fill``) — top-level
      ``{"status","avg_price","quantity"}`` with ``raw.source=strategy_executor``
    * **paper exit** (``direct_exit``) — top-level
      ``{"status","fill_price","filled_qty"}`` with ``raw.source=direct_exit``

    Returns ``None`` only when there is no response at all.
    """
    if not broker_response:
        return None

    raw = broker_response.get("raw")

    # Live Dhan: the broker's own order object lives under ``raw``.
    if isinstance(raw, dict) and "orderStatus" in raw:
        return FillInfo(
            status=_normalize_status(raw.get("orderStatus")),
            raw_status=_as_str(raw.get("orderStatus")),
            price=_to_decimal(raw.get("price")),
            qty=_to_int(raw.get("filledQty")),
            source="dhan",
        )

    # Paper exit (direct_exit simulated close).
    if "fill_price" in broker_response:
        return FillInfo(
            status=_normalize_status(broker_response.get("status")),
            raw_status=_as_str(broker_response.get("status")),
            price=_to_decimal(broker_response.get("fill_price")),
            qty=_to_int(broker_response.get("filled_qty")),
            source="paper_exit",
        )

    # Paper entry (strategy_executor simulated fill).
    if "avg_price" in broker_response:
        return FillInfo(
            status=_normalize_status(broker_response.get("status")),
            raw_status=_as_str(broker_response.get("status")),
            price=_to_decimal(broker_response.get("avg_price")),
            qty=_to_int(broker_response.get("quantity")),
            source="paper_entry",
        )

    return FillInfo(
        status=_normalize_status(broker_response.get("status")),
        raw_status=_as_str(broker_response.get("status")),
        price=None,
        qty=None,
        source="unknown",
    )


def _as_str(value: object) -> str | None:
    return None if value is None else str(value)


# ─── Core reconciliation (pure — no DB) ────────────────────────────────


def build_fill_index(
    executions: Iterable[StrategyExecution],
) -> dict[uuid.UUID, FillInfo]:
    """Map ``signal_id`` → real fill, de-duplicating the duplicate-row bug.

    Multiple ``strategy_executions`` rows can share one ``signal_id`` /
    broker order id (the "16 rows = 9 orders" duplication). They carry an
    identical fill, so the first parseable row per ``signal_id`` wins.
    """
    index: dict[uuid.UUID, FillInfo] = {}
    for execution in executions:
        sid = execution.signal_id
        if sid in index:
            continue
        fill = parse_fill(execution.broker_response)
        if fill is not None:
            index[sid] = fill
    return index


def reconcile_position(
    position: StrategyPosition,
    fills: dict[uuid.UUID, FillInfo],
    *,
    segment: str = DEFAULT_SEGMENT,
) -> RoundTrip:
    """Reconstruct one closed position's round trip + NET realized P&L.

    Entry and exit legs are linked through ``position.action_history`` (each
    event carries its ``signal_id``); fills come from ``fills`` (real broker
    fills). The trip is COMPLETE only when the entry filled, every close leg
    filled, and the close quantities sum to the position quantity.

    For a complete trip, estimated Indian derivatives charges (``segment``,
    default NFO) are computed and ``net_pnl = gross_pnl - costs.total``.
    """
    flags: list[str] = []
    side = str(position.side or "").strip().lower()
    direction = "long" if side == "buy" else "short" if side == "sell" else "unknown"
    if direction == "unknown":
        flags.append(f"unknown position side {position.side!r}")

    history: list[dict[str, Any]] = list(position.action_history or [])
    entry_events = [ev for ev in history if str(ev.get("action", "")).lower() == "entry"]
    exit_events = [ev for ev in history if str(ev.get("action", "")).lower() != "entry"]
    position_qty = int(position.total_quantity or 0)

    # Entry price: qty-weighted average over entry-leg REAL fills.
    entry_qty = 0
    entry_legs = 0
    entry_value = Decimal(0)
    entry_ok = True
    if not entry_events:
        flags.append("no entry leg recorded in action_history")
        entry_ok = False
    for event in entry_events:
        sid = _to_uuid(event.get("signal_id"))
        fill = fills.get(sid) if sid is not None else None
        qty = _to_int(event.get("qty")) or 0
        if fill is None:
            flags.append(f"entry leg {sid} has no execution fill in DB")
            entry_ok = False
            continue
        if fill.status != "FILLED" or fill.price is None:
            flags.append(f"entry leg {sid} not filled (status={fill.raw_status})")
            entry_ok = False
            continue
        entry_qty += qty
        entry_legs += 1
        entry_value += fill.price * qty
    entry_price = (entry_value / entry_qty) if entry_qty > 0 else None

    # Exit legs: realize P&L against the entry price.
    exits: list[ExitLeg] = []
    exit_qty_total = 0
    realized = Decimal(0)
    exits_ok = bool(exit_events)
    if not exit_events:
        flags.append("no close legs in action_history (still open or closed off-platform?)")
    for event in exit_events:
        sid = _to_uuid(event.get("signal_id"))
        fill = fills.get(sid) if sid is not None else None
        qty = _to_int(event.get("qty")) or 0
        leg_role = str(event.get("leg_role") or event.get("action") or "")
        if fill is None:
            flags.append(f"exit leg {leg_role} {sid} missing from DB (manual/external exit?)")
            exits.append(ExitLeg(leg_role, qty, None, "MISSING", sid, None))
            exits_ok = False
            continue
        if fill.status != "FILLED" or fill.price is None:
            flags.append(f"exit leg {leg_role} {sid} not filled (status={fill.raw_status})")
            exits.append(ExitLeg(leg_role, qty, fill.price, fill.status, sid, None))
            exits_ok = False
            continue
        leg_pnl: Decimal | None = None
        if entry_price is not None and direction in ("long", "short"):
            diff = fill.price - entry_price if direction == "long" else entry_price - fill.price
            leg_pnl = diff * qty
            realized += leg_pnl
        exit_qty_total += qty
        exits.append(ExitLeg(leg_role, qty, fill.price, fill.status, sid, leg_pnl))

    qty_match = position_qty > 0 and exit_qty_total == position_qty
    if exit_events and not qty_match:
        flags.append(f"close qty {exit_qty_total} != position qty {position_qty}")

    complete = (
        entry_ok
        and exits_ok
        and qty_match
        and entry_price is not None
        and direction in ("long", "short")
    )

    # Costs: estimate the Indian F&O charge stack and net it off the gross.
    gross_pnl = realized if complete else None
    costs: CostBreakdown | None = None
    net_pnl: Decimal | None = None
    if complete and gross_pnl is not None and entry_price is not None:
        exit_turnover = Decimal(0)
        for leg in exits:
            if leg.price is not None:
                exit_turnover += leg.price * leg.qty
        # ``entry_value`` is the real entry turnover (sum of fill.price * qty).
        if direction == "long":  # bought to open, sold to close
            buy_turnover, sell_turnover = entry_value, exit_turnover
        else:  # short: sold to open, bought to close
            buy_turnover, sell_turnover = exit_turnover, entry_value
        costs = compute_costs(
            buy_turnover=buy_turnover,
            sell_turnover=sell_turnover,
            orders=entry_legs + len(exits),
            segment=segment,
        )
        net_pnl = gross_pnl - costs.total

    return RoundTrip(
        position_id=position.id,
        symbol=str(position.symbol or ""),
        direction=direction,
        position_qty=position_qty,
        entry_legs=entry_legs,
        entry_price=entry_price,
        exits=exits,
        exit_qty_total=exit_qty_total,
        gross_pnl=gross_pnl,
        costs=costs,
        net_pnl=net_pnl,
        complete=complete,
        flags=flags,
    )


def reconcile(
    positions: Sequence[StrategyPosition],
    executions: Iterable[StrategyExecution],
    *,
    segment: str = DEFAULT_SEGMENT,
) -> list[RoundTrip]:
    """Pure reconciliation over already-loaded rows (no DB, no writes)."""
    index = build_fill_index(executions)
    return [reconcile_position(position, index, segment=segment) for position in positions]


# ─── DB layer (read + optional annotate) ───────────────────────────────


async def _load_closed_positions(
    session: AsyncSession, strategy_id: uuid.UUID
) -> list[StrategyPosition]:
    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.strategy_id == strategy_id,
            StrategyPosition.status == "closed",
        )
        .order_by(StrategyPosition.opened_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _load_executions(
    session: AsyncSession, strategy_id: uuid.UUID
) -> list[StrategyExecution]:
    stmt = (
        select(StrategyExecution)
        .join(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
        .where(StrategySignal.strategy_id == strategy_id)
        .order_by(StrategyExecution.placed_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def reconcile_strategy(
    session: AsyncSession,
    strategy_id: uuid.UUID,
    *,
    write: bool = False,
    segment: str = DEFAULT_SEGMENT,
) -> ReconcileResult:
    """Reconcile every CLOSED position of ``strategy_id``.

    Dry-run by default (``write=False``): computes + returns, writes nothing.
    With ``write=True`` it assigns ``final_pnl`` (NET of estimated costs) ONLY
    on positions whose round trip reconciles COMPLETELY, then commits.
    Incomplete trips are never written.
    """
    positions = await _load_closed_positions(session, strategy_id)
    executions = await _load_executions(session, strategy_id)
    index = build_fill_index(executions)

    trips: list[RoundTrip] = []
    annotated = 0
    for position in positions:
        trip = reconcile_position(position, index, segment=segment)
        trips.append(trip)
        if write and trip.complete and trip.net_pnl is not None:
            position.final_pnl = trip.net_pnl
            annotated += 1

    wrote = False
    if write and annotated:
        await session.commit()
        wrote = True
        _logger.info(
            "pnl_reconciler.annotated",
            extra={"strategy_id": str(strategy_id), "positions": annotated},
        )

    return ReconcileResult(strategy_id=strategy_id, trips=trips, annotated=annotated, wrote=wrote)


# ─── Going-forward recent scan (scheduled) ─────────────────────────────


async def _load_unrecorded_closed_positions(
    session: AsyncSession, *, since: datetime
) -> list[StrategyPosition]:
    """CLOSED positions with NULL ``final_pnl`` closed at/after ``since``.

    The ``closed_at >= since`` predicate is the GOING-FORWARD boundary: it
    scopes the scan to recently-closed trips and deliberately excludes
    historical / manual-era positions (also ``final_pnl IS NULL``) that
    closed before the window. Nothing here back-fills the past.
    """
    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.status == "closed",
            StrategyPosition.final_pnl.is_(None),
            StrategyPosition.closed_at.is_not(None),
            StrategyPosition.closed_at >= since,
        )
        .order_by(StrategyPosition.closed_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def plan_reconciliation(
    positions: Sequence[StrategyPosition],
    fills_by_strategy: dict[uuid.UUID, dict[uuid.UUID, FillInfo]],
    *,
    segment: str = DEFAULT_SEGMENT,
) -> list[RoundTrip]:
    """Pure: reconcile a cross-strategy batch of positions (no DB, no writes).

    Each position is reconciled against its own strategy's fill index.
    """
    return [
        reconcile_position(
            position, fills_by_strategy.get(position.strategy_id, {}), segment=segment
        )
        for position in positions
    ]


async def reconcile_unrecorded(
    session: AsyncSession,
    *,
    since: datetime,
    write: bool = False,
    segment: str = DEFAULT_SEGMENT,
) -> ReconcileResult:
    """Reconcile recently-CLOSED, not-yet-recorded positions (going-forward).

    Scans CLOSED positions with NULL ``final_pnl`` closed since ``since``,
    computes NET realized P&L per round trip from the real broker fills (gross
    minus estimated costs), and — in write mode only — annotates ``final_pnl``
    (NET) on the FULLY-reconciled ones. Dry-run (``write=False``, the scheduled
    default) writes nothing. Incomplete trips are never written. Historical
    trips outside the window are out of scope (see
    :func:`_load_unrecorded_closed_positions`).
    """
    positions = await _load_unrecorded_closed_positions(session, since=since)

    fills_by_strategy: dict[uuid.UUID, dict[uuid.UUID, FillInfo]] = {}
    for strategy_id in {position.strategy_id for position in positions}:
        executions = await _load_executions(session, strategy_id)
        fills_by_strategy[strategy_id] = build_fill_index(executions)

    trips = plan_reconciliation(positions, fills_by_strategy, segment=segment)

    annotated = 0
    if write:
        for position, trip in zip(positions, trips, strict=True):
            if trip.complete and trip.net_pnl is not None:
                position.final_pnl = trip.net_pnl
                annotated += 1

    wrote = False
    if write and annotated:
        await session.commit()
        wrote = True
        _logger.info("pnl_reconciler.annotated", extra={"positions": annotated})

    return ReconcileResult(strategy_id=None, trips=trips, annotated=annotated, wrote=wrote)


# ─── Reporting ─────────────────────────────────────────────────────────


def _fmt(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{value.quantize(_Q2):+,}" if value != 0 else "0.00"


def format_report(result: ReconcileResult, *, write: bool) -> str:
    """Render a human-readable per-trip + net summary."""
    mode = "WRITE" if write else "DRY-RUN"
    scope = f"strategy {result.strategy_id}" if result.strategy_id else "recent-scan"
    lines: list[str] = []
    lines.append(f"P&L Reconciler — {scope}  [{mode}]")
    lines.append(
        f"Closed positions: {len(result.trips)} | "
        f"complete: {len(result.complete_trips)} | "
        f"incomplete: {len(result.incomplete_trips)}"
    )
    lines.append("-" * 72)
    for trip in result.trips:
        tag = "OK  " if trip.complete else "SKIP"
        entry = trip.entry_price.quantize(_Q2) if trip.entry_price is not None else "—"
        lines.append(
            f"[{tag}] {trip.symbol} {trip.direction} qty {trip.position_qty} entry {entry}"
        )
        if trip.costs is not None:
            c = trip.costs
            lines.append(
                f"        gross {_fmt(trip.gross_pnl)}  - costs {c.total} (est)"
                f"  = net {_fmt(trip.net_pnl)}"
            )
            lines.append(
                f"        costs[{c.segment}]: brk {c.brokerage} stt {c.stt} "
                f"exch {c.exchange_txn} sebi {c.sebi_fee} stamp {c.stamp_duty} "
                f"gst {c.gst}  (orders={c.orders})"
            )
        else:
            lines.append(f"        gross {_fmt(trip.gross_pnl)}  (incomplete — not costed)")
        for flag in trip.flags:
            lines.append(f"        ! {flag}")
    lines.append("-" * 72)
    lines.append(
        f"TOTAL (complete trips): gross {_fmt(result.gross_realized)}  "
        f"- costs {result.total_costs}  = net {_fmt(result.net_realized)}  "
        f"[costs ESTIMATED]"
    )
    if write:
        lines.append(f"Annotated final_pnl (NET) on {result.annotated} position(s).")
    else:
        lines.append(
            f"Dry-run: nothing written. Would annotate {len(result.complete_trips)} position(s)."
        )
    return "\n".join(lines)
