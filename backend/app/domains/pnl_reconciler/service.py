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
   ``broker_response`` — Dhan ``raw.{orderStatus,averageTradedPrice,filledQty}``
   for live (``raw.price`` is the order's LIMIT price, never the fill), the
   paper-sim ``avg_price`` / ``fill_price`` shapes for paper. NEVER the
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
from app.domains.pnl_reconciler.attribution import (
    BOT_CORRELATION_IDS,
    TAG_HUMAN_INTERFERED,
    TAG_PAPER_SIM,
    TAG_UNPRICEABLE,
    AccountFill,
    Attribution,
    attribute,
)
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
    #: The broker's own order id (Dhan ``orderId``). Brokerage is flat PER
    #: ORDER, so this is what de-duplicates legs for costing: N action_history
    #: events that map to ONE broker order are ONE ₹20 charge, not N. ``None``
    #: for paper fills and unknown shapes, which then count per leg as before.
    order_id: str | None = None
    #: Dhan ``correlationId``. The bot stamps ``strategy-engine`` /
    #: ``strategy-engine-direct-exit``; anything else on the same contract is
    #: the founder's manual activity (rule 3, 2026-09-04). ``None`` for paper.
    correlation_id: str | None = None

    @property
    def is_live(self) -> bool:
        return self.source == "dhan"


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
    #: Founder's exit rule outcome (see :mod:`attribution`). ``None`` when the
    #: account's trade book was not supplied — a LIVE trip is then never
    #: written (fail closed); a PAPER trip has no manual book and is tagged
    #: ``paper_sim`` from its own fills (never counted by a live ledger).
    attribution: Attribution | None = None
    #: One of ``ATTRIBUTION_TAGS`` — what ``strategy_positions.pnl_attribution``
    #: receives in write mode. ``None`` == "not attributable yet".
    attribution_tag: str | None = None
    attribution_detail: str | None = None
    #: True when every fill in the trip is a Dhan (live) fill.
    live: bool = False

    @property
    def writable(self) -> bool:
        """A priced trip the write path may record: paper strict-complete, or a
        live trip the founder's rule priced from the account's book."""
        if not self.complete or self.net_pnl is None:
            return False
        if self.live:
            return self.attribution is not None and self.attribution.priced
        return True


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

    * **Dhan (live)** — ``{"raw": {"orderStatus","averageTradedPrice","filledQty",...}, ...}``
      (``raw.price`` is the LIMIT price and is never used)
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
            # The FILL is ``averageTradedPrice``. ``raw["price"]`` is the order's
            # LIMIT price (the executor's slippage buffer, Rs 13-42 away from the
            # fill on every live order) and was what this read until
            # 2026-09-04 — every written final_pnl was wrong by that buffer,
            # always against the strategy. Never fall back to ``price``: a
            # traded order with no ATP is unpriceable, not approximately priced.
            price=_dhan_traded_price(raw),
            qty=_to_int(raw.get("filledQty")),
            source="dhan",
            order_id=_as_str(raw.get("orderId")),
            correlation_id=_as_str(raw.get("correlationId")),
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


def _dhan_traded_price(raw: dict[str, Any]) -> Decimal | None:
    """The price Dhan actually FILLED an order at — ``averageTradedPrice``.

    ``raw["price"]`` is deliberately ignored: on a Dhan order object it is the
    LIMIT price the executor sent (fill ± slippage buffer), never the trade.
    A zero/absent ATP (unfilled, or an older response shape) yields ``None``
    so the trip is flagged incomplete rather than priced at the limit.
    """
    atp = _to_decimal(raw.get("averageTradedPrice"))
    if atp is None or atp <= 0:
        return None
    return atp


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
    account_fills: Sequence[AccountFill] | None = None,
) -> RoundTrip:
    """Reconstruct one closed position's round trip + NET realized P&L.

    Entry and exit legs are linked through ``position.action_history`` (each
    event carries its ``signal_id``); fills come from ``fills`` (real broker
    fills). The trip is COMPLETE only when the entry filled, every close leg
    filled, and the close quantities sum to the position quantity.

    For a complete trip, estimated Indian derivatives charges (``segment``,
    default NFO) are computed and ``net_pnl = gross_pnl - costs.total``.

    **Founder's exit rule (2026-09-04).** When ``account_fills`` — the whole
    account's futures fills from the broker's trade book — is supplied, a
    LIVE trip is re-priced by :func:`attribution.attribute`: the trade closes
    when the account goes flat on the contract by ANY fill, provided no manual
    lots predate the bot's entry and no fill increased exposure before the
    flat point; otherwise the trip is ``human_interfered`` (NULL, tagged) and
    the strict bot-only numbers are discarded. Without ``account_fills`` a
    live trip keeps its strict numbers for reporting but is NOT writable.
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
    # Brokerage de-dup: one flat charge per DISTINCT broker order. A leg with
    # no broker order id (paper, unknown shape) is counted on its own, so the
    # old per-leg behaviour is the floor, never exceeded.
    order_keys: set[str] = set()
    unkeyed_orders = 0

    def _count_order(fill: FillInfo) -> None:
        nonlocal unkeyed_orders
        if fill.order_id:
            order_keys.add(fill.order_id)
        else:
            unkeyed_orders += 1

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
        _count_order(fill)
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
        _count_order(fill)

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
        # WAS ``entry_legs + len(exits)`` — one charge per action_history
        # EVENT. A single Dhan order the engine logged as several leg events
        # was costed several times over, and that number was headed for the
        # public verified record with no correction path.
        costs = compute_costs(
            buy_turnover=buy_turnover,
            sell_turnover=sell_turnover,
            orders=len(order_keys) + unkeyed_orders,
            segment=segment,
        )
        net_pnl = gross_pnl - costs.total

    trip = RoundTrip(
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
    _classify_trip(trip, position, fills, segment=segment, account_fills=account_fills)
    return trip


def _trip_fills(position: StrategyPosition, fills: dict[uuid.UUID, FillInfo]) -> list[FillInfo]:
    out: list[FillInfo] = []
    for event in position.action_history or []:
        sid = _to_uuid(event.get("signal_id"))
        fill = fills.get(sid) if sid is not None else None
        if fill is not None:
            out.append(fill)
    return out


def _classify_trip(
    trip: RoundTrip,
    position: StrategyPosition,
    fills: dict[uuid.UUID, FillInfo],
    *,
    segment: str,
    account_fills: Sequence[AccountFill] | None,
) -> None:
    """Attach the founder's-rule attribution to ``trip`` (mutates in place).

    * No ``account_fills`` (the scheduled scan, or a paper strategy):
      a PAPER trip (no Dhan fill) is priced from its simulated fills and
      tagged ``paper_sim`` (never counted by a live ledger); a LIVE trip has
      nothing to attribute against — ``attribution`` stays ``None`` and it is
      never writable.
    * With ``account_fills`` (a live strategy reconciled by the founder):
      EVERY trip is attributed against the account's book. A priced outcome
      REPLACES gross / costs / net / complete with the account-level numbers;
      ``human_interfered`` / ``unpriceable`` clear them. A paper-era test row
      on a live strategy has no fill in the broker's book → ``unpriceable``,
      so a simulated P&L can never enter the live record.
    """
    trip_fills = _trip_fills(position, fills)
    trip.live = any(f.is_live for f in trip_fills)
    if account_fills is None:
        if trip.live:
            trip.flags.append(
                "attribution required: live trip — supply the account's trade book "
                "(--tradebook) to price it under the founder's exit rule; NOT written"
            )
            return
        trip.attribution_tag = TAG_PAPER_SIM if trip.complete else TAG_UNPRICEABLE
        trip.attribution_detail = (
            "paper trip: simulated fills, no manual book"
            if trip.complete
            else "paper trip could not be reconstructed: " + "; ".join(trip.flags)
        )
        return

    # Entry order ids = the bot's FILLED entry legs; bot order ids = every
    # fill of this strategy that carries a bot correlationId.
    history: list[dict[str, Any]] = list(position.action_history or [])
    entry_order_ids: set[str] = set()
    for event in history:
        if str(event.get("action", "")).lower() != "entry":
            continue
        sid = _to_uuid(event.get("signal_id"))
        fill = fills.get(sid) if sid is not None else None
        if fill is not None and fill.status == "FILLED" and fill.order_id:
            entry_order_ids.add(fill.order_id)
    bot_order_ids = {
        f.order_id
        for f in fills.values()
        if f.order_id and (f.correlation_id in BOT_CORRELATION_IDS or f.correlation_id is None)
    }
    outcome = attribute(entry_order_ids, account_fills, bot_order_ids=bot_order_ids)
    trip.attribution = outcome
    trip.attribution_tag = outcome.tag
    trip.attribution_detail = outcome.reason

    if not outcome.priced:
        if trip.complete:
            trip.flags.append(
                f"strict bot-only trip discarded under the founder's exit rule → {outcome.tag}"
            )
        trip.complete = False
        trip.gross_pnl = None
        trip.costs = None
        trip.net_pnl = None
        return

    # Priced from the account's book: entry fills + the fills that took the
    # account flat (bot or manual). Costs on the attributed turnover.
    direction = "long" if outcome.entry_fills[0].side.upper() == "BUY" else "short"
    entry_turnover, exit_turnover = outcome.entry_turnover, outcome.exit_turnover
    buy_turnover, sell_turnover = (
        (entry_turnover, exit_turnover) if direction == "long" else (exit_turnover, entry_turnover)
    )
    costs = compute_costs(
        buy_turnover=buy_turnover,
        sell_turnover=sell_turnover,
        orders=outcome.distinct_orders,
        segment=segment,
    )
    assert outcome.gross_pnl is not None
    trip.direction = direction
    trip.entry_price = entry_turnover / outcome.entry_qty
    trip.entry_legs = len(outcome.entry_fills)
    trip.exits = [
        ExitLeg(
            leg_role="account_flat" if f.order_id not in bot_order_ids else "bot_exit",
            qty=f.qty,
            price=f.price,
            status="FILLED",
            signal_id=None,
            realized_pnl=(
                (f.price - trip.entry_price) * f.qty
                if direction == "long"
                else (trip.entry_price - f.price) * f.qty
            ),
        )
        for f in outcome.exit_fills
    ]
    trip.exit_qty_total = sum(f.qty for f in outcome.exit_fills)
    trip.gross_pnl = outcome.gross_pnl
    trip.costs = costs
    trip.net_pnl = outcome.gross_pnl - costs.total
    trip.complete = True


def reconcile(
    positions: Sequence[StrategyPosition],
    executions: Iterable[StrategyExecution],
    *,
    segment: str = DEFAULT_SEGMENT,
    account_fills: Sequence[AccountFill] | None = None,
) -> list[RoundTrip]:
    """Pure reconciliation over already-loaded rows (no DB, no writes)."""
    index = build_fill_index(executions)
    return [
        reconcile_position(position, index, segment=segment, account_fills=account_fills)
        for position in positions
    ]


def apply_write(position: StrategyPosition, trip: RoundTrip, *, overwrite: bool) -> str | None:
    """Record ``trip`` on ``position`` per the write rules; returns what changed.

    * writable trip → ``final_pnl`` = NET (only if NULL, or ``overwrite``);
    * ``human_interfered`` → ``final_pnl`` set to NULL under ``overwrite``
      (a value written before the rule existed is wrong by construction);
    * ``unpriceable`` with a stored literal ``0`` → NULL under ``overwrite``
      (a zero is never a priced trip — "never let a zero reach the record");
    * the attribution tag + detail are always stamped when known.

    Returns ``"pnl"``, ``"nulled"``, ``"tag"`` or ``None`` (nothing changed).
    """
    changed: str | None = None
    if trip.writable and trip.net_pnl is not None:
        may_write = position.final_pnl is None or overwrite
        if may_write and position.final_pnl != trip.net_pnl:
            position.final_pnl = trip.net_pnl
            changed = "pnl"
    elif overwrite and position.final_pnl is not None:
        tag = trip.attribution_tag
        if tag == TAG_HUMAN_INTERFERED or (tag == TAG_UNPRICEABLE and position.final_pnl == 0):
            position.final_pnl = None
            changed = "nulled"
    if trip.attribution_tag is not None and (
        position.pnl_attribution != trip.attribution_tag
        or position.pnl_attribution_detail != trip.attribution_detail
    ):
        position.pnl_attribution = trip.attribution_tag
        position.pnl_attribution_detail = trip.attribution_detail
        changed = changed or "tag"
    return changed


# ─── DB layer (read + optional annotate) ───────────────────────────────


async def _load_closed_positions(
    session: AsyncSession, strategy_id: uuid.UUID
) -> list[StrategyPosition]:
    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.strategy_id == strategy_id,
            StrategyPosition.status == "closed",
            # The OWNER's record only. Marketplace subscriber positions share
            # strategy_id (subscription_id NOT NULL) and must never be folded
            # into the creator's published numbers.
            StrategyPosition.subscription_id.is_(None),
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
        .where(
            StrategySignal.strategy_id == strategy_id,
            # Owner fills only: a subscriber's paper fill shares the owner's
            # signal_id (subscription_id NOT NULL) and must never price the
            # owner's trip. Mirrors the position scoping above.
            StrategyExecution.subscription_id.is_(None),
        )
        .order_by(StrategyExecution.placed_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def reconcile_strategy(
    session: AsyncSession,
    strategy_id: uuid.UUID,
    *,
    write: bool = False,
    overwrite: bool = False,
    segment: str = DEFAULT_SEGMENT,
    account_fills: Sequence[AccountFill] | None = None,
) -> ReconcileResult:
    """Reconcile every CLOSED position of ``strategy_id``.

    Dry-run by default (``write=False``): computes + returns, writes nothing.
    With ``write=True`` it records ``final_pnl`` (NET of estimated costs) ONLY
    on positions whose trip is *writable* (see :attr:`RoundTrip.writable`:
    paper strict-complete, or LIVE and priced under the founder's exit rule
    from ``account_fills``) and whose ``final_pnl`` is still NULL
    (append-only), then commits. ``overwrite=True`` is the explicit CORRECTION
    path: it recomputes writable trips even when a value exists, NULLs a value
    on a trip the rule marks ``human_interfered``, and NULLs a stored literal
    zero on an ``unpriceable`` trip. The attribution tag + detail are stamped
    on every classified position. A live trip without ``account_fills`` is
    never written. The public showcase count moves the moment a value is
    written — treat every write as a publication.
    """
    positions = await _load_closed_positions(session, strategy_id)
    executions = await _load_executions(session, strategy_id)
    index = build_fill_index(executions)

    trips: list[RoundTrip] = []
    annotated = 0
    for position in positions:
        trip = reconcile_position(position, index, segment=segment, account_fills=account_fills)
        trips.append(trip)
        if write and apply_write(position, trip, overwrite=overwrite) is not None:
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

    # FAIL CLOSED for live money: the scheduled scan has no trade book, so a
    # LIVE trip is never writable here (``RoundTrip.writable``); only PAPER
    # trips can be recorded by the beat. Live trips are priced by the
    # founder-run CLI with ``--tradebook``.
    annotated = 0
    if write:
        for position, trip in zip(positions, trips, strict=True):
            if apply_write(position, trip, overwrite=False) is not None:
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


def _bot_ids(trip: RoundTrip) -> set[str]:
    """Order ids the report labels BOT: the trip's own exits that are not manual."""
    if trip.attribution is None:
        return set()
    return {
        f.order_id
        for f, leg in zip(trip.attribution.exit_fills, trip.exits, strict=False)
        if leg.leg_role != "account_flat"
    } | {f.order_id for f in trip.attribution.entry_fills}


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
        pid = str(trip.position_id)[:8] if trip.position_id else "—"
        lines.append(
            f"[{tag}] {pid} {trip.symbol} {trip.direction} qty {trip.position_qty} entry {entry}"
            f"  attribution={trip.attribution_tag or 'n/a'}"
        )
        if trip.attribution is not None:
            for f in trip.attribution.entry_fills:
                lines.append(f"        entry {f.describe(bot_order_ids=_bot_ids(trip))}")
            for f in trip.attribution.exit_fills:
                lines.append(f"        exit  {f.describe(bot_order_ids=_bot_ids(trip))}")
            lines.append(f"        rule: {trip.attribution.reason}")
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
