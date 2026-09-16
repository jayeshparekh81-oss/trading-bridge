"""Strategy-engine positions API — list + kill switch.

The kill-switch endpoint here is the strategy-engine variant: it closes
every open ``StrategyPosition`` for the calling user and marks any
``received`` / ``validating`` signals as rejected so an in-flight AI
call cannot turn into an order after the user has hit the brake.

This is distinct from :mod:`app.api.kill_switch` which is the platform-
wide circuit breaker — both can coexist.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core import redis_client
from app.core.logging import get_logger
from app.core.tracking_epoch import positions_in_record
from app.db.models.kill_switch import KillSwitchEvent
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.domains.pnl_reconciler.costs import DEFAULT_SEGMENT, compute_costs
from app.schemas.kill_switch import TripReason
from app.schemas.strategy_position import (
    KillSwitchResponse,
    StrategyPositionListResponse,
    StrategyPositionRead,
)
from app.services import broker_resting_stops, pnl_service

# The trip-meta key helper lives in the kill-switch service. It is imported,
# never modified — app/api/kill_switch.py:manual_trip already imports
# ``_reset_token_key`` from the same module, so this is the established way to
# share the key shape rather than re-spelling it here and letting the two drift.
from app.services.kill_switch_service import _TRIP_META_TTL, _trip_meta_key
from app.services.position_manager import close_position_now

logger = get_logger("app.api.strategy_positions")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])

# ─── Derived exit price + realised P&L on the closed portion ────────────
#
# ``strategy_positions`` has NO exit-price column and no realised column for
# a PARTIAL — ``final_pnl`` is written by the reconciler for ``status=closed``
# rows only. Both are DERIVED here from the position's own order legs in
# ``strategy_executions``, per request, and stored nowhere.
#
# Provenance of the leg price: ``strategy_executions.price`` on both the entry
# and the close legs is the broker's CONFIRMED average traded price
# (``confirm_fill(...).avg_price`` — see strategy_executor / direct_exit), not
# the requested or TradingView payload price. That is why the derivation reads
# the legs and never ``position.avg_entry_price``.

_Q2 = Decimal("0.01")
_Q4 = Decimal("0.0001")

#: The ONE entry role. Every other ``leg_role`` the engine writes is a close:
#: ``direct_partial`` / ``direct_exit`` / ``direct_sl`` (Pine-driven) and
#: ``partial_target`` / ``trailing_sl`` / ``hard_sl`` / ``circuit_breaker`` /
#: ``kill_switch`` (position-manager driven). Treating "not entry" as a close
#: is deliberate: a NEW exit role must not silently vanish from the exit price.
_ENTRY_ROLE = "entry"
#: ``leg_role`` used for an operator's disclosed, non-broker exit. Matches the
#: value written into ``action_history`` when a position is reconciled by hand.
_OPERATOR_RECONCILE_ROLE = "operator_reconcile"


@dataclass(frozen=True)
class PositionLeg:
    """One ``strategy_executions`` row, reduced to what pricing needs.

    Deliberately does NOT carry ``broker_response`` — the raw Dhan envelope is
    never loaded here, let alone serialised to a client.
    """

    leg_role: str
    quantity: int
    price: Decimal | None
    broker_order_id: str | None
    #: False for a leg that is NOT a broker fill — a quantity an operator
    #: recorded as closed with no order behind it, reconstructed in memory from
    #: the position's own ``action_history``. It is never a
    #: ``strategy_executions`` row and never carries a fabricated
    #: ``broker_order_id``.
    #:
    #: Its presence makes the row UNPRICEABLE from our own legs (see
    #: :func:`derive_position_figures`) — that is its whole purpose. It exists
    #: so the row knows that quantity left and can say why it cannot price it,
    #: rather than silently averaging over the fills it does have.
    broker_fill: bool = True


@dataclass(frozen=True)
class DerivedFigures:
    """What the row can honestly say about its own exit, and why."""

    exit_price: Decimal | None
    realised_pnl: Decimal | None  # net of estimated charges
    gross_pnl: Decimal | None
    charges: Decimal | None
    quantity: int | None  # the closed portion this prices
    reason: str  # basis when computed, WHY when NULL — never blank


def _q(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _count_orders(legs: Iterable[PositionLeg]) -> int:
    """Number of REAL broker orders these legs represent.

    Dhan bills brokerage per EXECUTED ORDER, so the four 200-lot entry rows
    that share one ``broker_order_id`` are ONE ₹20 charge, not four — while a
    partial exit is its own order and carries its own charge. A leg with no
    order id (paper, unknown shape) counts on its own, so per-leg counting is
    the floor and is never exceeded. Same de-dup rule as the reconciler.

    A leg that is not a broker fill (``broker_fill=False`` — an operator's
    disclosed estimate) is skipped entirely: Dhan never billed for an order
    that was never placed, so charging one would invent a cost to go with the
    invented fill.
    """
    keyed: set[str] = set()
    unkeyed = 0
    for leg in legs:
        if not leg.broker_fill:
            continue
        if leg.broker_order_id:
            keyed.add(leg.broker_order_id)
        else:
            unkeyed += 1
    return len(keyed) + unkeyed


def derive_position_figures(
    *,
    side: str | None,
    total_quantity: int,
    remaining_quantity: int,
    legs: Sequence[PositionLeg],
    pnl_attribution: str | None = None,
    segment: str = DEFAULT_SEGMENT,
) -> DerivedFigures:
    """Derive the exit price and the realised P&L on the CLOSED portion.

    Rules, all of them the founder's:

    * The exit price is the quantity-weighted mean of the close legs. If ANY
      close leg is unpriced, or the close quantities do not add up to the
      quantity that actually left the position, NOTHING is returned — a mean
      over the resolvable subset would be a guess dressed as a fact.
    * The realised figure prices the closed portion, including the closed part
      of a PARTIAL. It is NET: gross minus the estimated Indian F&O charge
      stack from :mod:`app.domains.pnl_reconciler.costs` (the arithmetic lives
      there and is not repeated here).
    * Charges are counted PER REAL BROKER ORDER — never pro-rata, never spread
      across portions. The entry order's flat brokerage was billed once, in
      full, at entry, so it is carried in full here; the turnover-based
      statutory charges are computed on the turnover of the closed portion,
      which is what those charges are actually levied on.
    * When the figure cannot be computed, it is NULL **and the row says why**.

    ``pnl_attribution`` is used for wording only. A ``human_interfered`` tag is
    an ACCOUNT-level verdict (the founder's manual fills on the same contract);
    it does not erase the bot's own legs, so the closed portion is still priced
    and the wording says exactly whose legs the number came from.
    """
    direction = str(side or "").strip().lower()
    entry_legs = [leg for leg in legs if leg.leg_role.strip().lower() == _ENTRY_ROLE]
    exit_legs = [leg for leg in legs if leg.leg_role.strip().lower() != _ENTRY_ROLE]
    closed_qty = int(total_quantity or 0) - int(remaining_quantity or 0)

    def _nothing(reason: str, *, exit_price: Decimal | None = None) -> DerivedFigures:
        return DerivedFigures(
            exit_price=exit_price,
            realised_pnl=None,
            gross_pnl=None,
            charges=None,
            quantity=None,
            reason=reason,
        )

    # ── The exit price ────────────────────────────────────────────────
    if not exit_legs:
        if closed_qty <= 0:
            return _nothing("still open — nothing has exited yet")
        return _nothing(
            f"{closed_qty} left the position but no exit leg is recorded "
            "against it (closed off-platform?)"
        )

    # NEVER ESTIMATE (founder's standing rule). A portion closed with no broker
    # fill behind it cannot be priced, and the row says so instead of showing a
    # number. This is checked BEFORE the generic unpriced guard so the reason
    # names the real situation rather than "a leg has no price".
    unfilled = [leg for leg in exit_legs if not leg.broker_fill]
    if unfilled:
        unfilled_qty = sum(int(leg.quantity or 0) for leg in unfilled)
        return _nothing(
            f"{unfilled_qty} of {closed_qty} left this position with NO BROKER "
            "FILL behind it (closed by an operator, or at the broker outside "
            "this platform), so no exit price and no P&L can be derived from "
            "our own legs — the value stays empty rather than being estimated. "
            "Price it from the account's trade book."
        )

    unpriced = [leg for leg in exit_legs if leg.price is None]
    if unpriced:
        return _nothing(
            f"{len(unpriced)} of {len(exit_legs)} exit legs have no recorded "
            "price — a mean over the rest would be a guess"
        )

    exit_qty = sum(int(leg.quantity or 0) for leg in exit_legs)
    if exit_qty <= 0:
        return _nothing("exit legs carry no quantity")

    # Every exit leg is priced here — the ``unpriced`` guard above returned.
    exit_value = Decimal(0)
    for leg in exit_legs:
        if leg.price is not None:
            exit_value += leg.price * int(leg.quantity or 0)
    exit_price = _q(exit_value / exit_qty, _Q4)

    if closed_qty <= 0 or exit_qty != closed_qty:
        # The exit price still describes the legs we DO have, so it is
        # returned; the P&L is not, because the quantity it would price is in
        # dispute between the legs and the position row.
        return _nothing(
            f"exit legs cover {exit_qty} but {closed_qty} has left the "
            "position — quantities do not reconcile",
            exit_price=exit_price,
        )

    # ── The realised figure on that closed quantity ───────────────────
    if direction not in ("buy", "sell"):
        return _nothing(f"unknown position side {side!r}", exit_price=exit_price)
    if not entry_legs:
        return _nothing(
            "no entry leg is recorded — the closed portion cannot be priced",
            exit_price=exit_price,
        )
    if any(leg.price is None for leg in entry_legs):
        return _nothing(
            "an entry leg has no recorded price — the closed portion cannot "
            "be priced",
            exit_price=exit_price,
        )
    entry_qty = sum(int(leg.quantity or 0) for leg in entry_legs)
    if entry_qty <= 0:
        return _nothing("entry legs carry no quantity", exit_price=exit_price)

    # Every entry leg is priced here — the ``any(...)`` guard above returned.
    entry_value = Decimal(0)
    for leg in entry_legs:
        if leg.price is not None:
            entry_value += leg.price * int(leg.quantity or 0)
    entry_price = entry_value / entry_qty

    if direction == "buy":  # long: bought to open, sold to close
        gross = exit_value - entry_price * closed_qty
        buy_turnover = entry_price * closed_qty
        sell_turnover = exit_value
    else:  # short: sold to open, bought to close
        gross = entry_price * closed_qty - exit_value
        buy_turnover = exit_value
        sell_turnover = entry_price * closed_qty

    costs = compute_costs(
        buy_turnover=buy_turnover,
        sell_turnover=sell_turnover,
        orders=_count_orders(list(entry_legs) + list(exit_legs)),
        segment=segment,
    )
    gross_q = _q(gross, _Q2)
    net = _q(gross_q - costs.total, _Q2)

    portion = (
        f"the closed {closed_qty} of {total_quantity}"
        if closed_qty != int(total_quantity or 0)
        else f"all {closed_qty}"
    )
    # Every leg reaching here IS a broker fill — the unfilled guard above
    # returned otherwise — so the figure is fill-sourced by construction.
    reason = (
        f"derived from the bot's own legs on {portion}: entry "
        f"{_q(entry_price, _Q4)}, exit {exit_price}; net of estimated charges "
        f"({costs.total}) on {costs.orders} broker order(s)"
    )
    tag = (pnl_attribution or "").strip().lower()
    if tag and tag != "bot_only":
        # Say whose legs this is, so nobody reads it as the account's number.
        reason += (
            f"; the account-level attribution ({tag}) is a verdict on the "
            "ACCOUNT and is not applied to this bot-leg figure"
        )

    return DerivedFigures(
        exit_price=exit_price,
        realised_pnl=net,
        gross_pnl=gross_q,
        charges=costs.total,
        quantity=closed_qty,
        reason=reason,
    )


def _unfilled_legs_from_history(history: Any) -> list[PositionLeg]:
    """Exit legs an OPERATOR recorded by hand — carried WITHOUT a price.

    🔴 THESE ARE NOT ROWS, AND AS OF 2026-09-16 THEY ARE NOT PRICES EITHER.

    When a position is closed by an operator because the engine's exit was
    never dispatched, there is no broker order and so no
    ``strategy_executions`` row — deliberately, because inserting one would
    fabricate a broker order in the log we reconcile against Dhan.

    Between 11 and 16 Sep this function returned the operator's recorded
    ``exit_price`` as a real leg, so the row's exit price and realised figure
    were computed partly from a number no broker ever filled. On d0086394 that
    published 3287.65 as an exit price and 41,769.71 as a realised figure, 61%
    of which came from a level the engine imagined. A real fill for that
    quantity existed the whole time (order 35226091145606, BUY 200 @3215.40,
    11 Sep 09:31:17 IST); nobody looked, because the row already had a number.

    The founder's rule governs: *every P&L must come from an actual Dhan fill;
    if a fill cannot be found the value stays NULL with a reason, never a
    guess.* So the event is still READ — the row must know its quantity left
    and must say why it cannot be priced — but it is carried with
    ``price=None``. :func:`derive_position_figures` then refuses to price the
    portion and says so, which is the honest output.

    Only events that are explicitly an operator reconcile AND explicitly not a
    broker fill are read. An event missing its quantity is skipped rather than
    guessed at.
    """
    out: list[PositionLeg] = []
    for event in history or []:
        if not isinstance(event, dict):
            continue
        if event.get("broker_fill") is not False:
            continue
        if str(event.get("leg_role") or "").strip().lower() != _OPERATOR_RECONCILE_ROLE:
            continue
        raw_qty = event.get("qty")
        if raw_qty is None:
            continue
        try:
            qty = int(raw_qty)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        out.append(
            PositionLeg(
                leg_role=_OPERATOR_RECONCILE_ROLE,
                quantity=qty,
                # NEVER the operator's recorded exit_price. See the docstring.
                price=None,
                broker_order_id=None,
                broker_fill=False,
            )
        )
    return out


def _signal_ids_from_history(history: Any) -> list[uuid.UUID]:
    """Signal ids a position's ``action_history`` points at, in order.

    ``action_history`` is the position → signal map (each event carries its
    own ``signal_id``); this is the same exact-id chain the reconciler walks,
    never a time window.
    """
    out: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for event in history or []:
        if not isinstance(event, dict):
            continue
        raw = event.get("signal_id")
        if raw in (None, ""):
            continue
        try:
            sid = raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
        except (AttributeError, TypeError, ValueError):
            continue
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


async def _legs_by_signal(
    db: AsyncSession, signal_ids: set[uuid.UUID]
) -> dict[uuid.UUID, list[PositionLeg]]:
    """ONE query for the whole page's legs — never one per row.

    Columns are named explicitly so ``broker_response`` (the raw Dhan
    envelope) is not even read out of the database on a page load.

    ``subscription_id IS NULL`` is REQUIRED, not decoration: marketplace
    fan-out writes subscriber PAPER executions against the OWNER's signal id
    (marketplace_fanout.py), so without the filter a subscriber's simulated
    fill would be averaged into the owner's real exit price.
    """
    if not signal_ids:
        return {}
    stmt = select(
        StrategyExecution.signal_id,
        StrategyExecution.leg_role,
        StrategyExecution.quantity,
        StrategyExecution.price,
        StrategyExecution.broker_order_id,
    ).where(
        StrategyExecution.signal_id.in_(signal_ids),
        StrategyExecution.subscription_id.is_(None),
        # A leg that errored never filled, so it can never be part of a price.
        # Nothing in the live path writes ``error_code`` today; this is the
        # guard for the day something does, and it fails SAFE — a dropped leg
        # breaks the quantity reconciliation, so the row returns NULL + a
        # reason instead of a price computed from a subset.
        StrategyExecution.error_code.is_(None),
    )
    out: dict[uuid.UUID, list[PositionLeg]] = {}
    for sid, leg_role, quantity, price, broker_order_id in await db.execute(stmt):
        out.setdefault(sid, []).append(
            PositionLeg(
                leg_role=str(leg_role or ""),
                quantity=int(quantity or 0),
                price=price,
                broker_order_id=broker_order_id or None,
            )
        )
    return out


@router.get("/positions", response_model=StrategyPositionListResponse)
async def list_positions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
) -> StrategyPositionListResponse:
    """List the current user's OWN positions, newest first.

    Owner-scoped: ``subscription_id IS NULL`` excludes marketplace fan-out
    subscriber (paper) positions, which carry a non-NULL ``subscription_id`` +
    the subscriber's ``user_id``. Without this they would appear UNLABELED in
    the subscriber's own positions view once ``MARKETPLACE_FANOUT_ENABLED``
    flips. This is the user's OWN trading view; per-subscription subscriber
    views are a separate, additive endpoint (later). Mirrors the internal owner
    lookups, which already filter ``subscription_id IS NULL``.
    """
    stmt = (
        select(StrategyPosition)
        .where(
            StrategyPosition.user_id == current_user.id,
            StrategyPosition.subscription_id.is_(None),
            # The tracking cut-off — REPORTING ONLY, and it stops here.
            # The kill-switch select ~90 lines below is a near-identical
            # statement over the same table and MUST NOT get this filter.
            positions_in_record(),
        )
        .order_by(StrategyPosition.opened_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(StrategyPosition.status == status_filter)

    rows = (await db.execute(stmt)).scalars().all()
    items = [StrategyPositionRead.model_validate(r) for r in rows]

    # Derived exit price + realised-on-the-closed-portion.
    #
    # Cost discipline: ONE extra query for the WHOLE page (never one per row)
    # and NO broker call — a page load must not reach Dhan, and it must not
    # walk the executions table N times.
    history_by_row = [_signal_ids_from_history(r.action_history) for r in rows]
    all_signal_ids = {sid for ids in history_by_row for sid in ids}
    legs_map = await _legs_by_signal(db, all_signal_ids)
    for item, row, sig_ids in zip(items, rows, history_by_row, strict=True):
        legs: list[PositionLeg] = []
        for sid in sig_ids:
            legs.extend(legs_map.get(sid, ()))
        # An operator's hand-recorded exit has no execution row by design, so
        # it is reconstructed from this row's own action_history. In memory
        # only, and WITHOUT a price — see _unfilled_legs_from_history.
        legs.extend(_unfilled_legs_from_history(row.action_history))
        derived = derive_position_figures(
            side=row.side,
            total_quantity=row.total_quantity,
            remaining_quantity=row.remaining_quantity,
            legs=legs,
            pnl_attribution=row.pnl_attribution,
        )
        item.exit_price = derived.exit_price
        # ONE P&L PER ROW. ``final_pnl`` is the reconciler's number, priced from
        # the whole ACCOUNT's trade book; the derived figure is priced from OUR
        # execution legs alone. When both exist they can disagree — and on
        # 844b8037 they did, by 119.94, because the leg that actually closed it
        # was pine_replica's stop @3415.50, which never reaches our table, so
        # the derived figure used the 04-Sep SL_HIT @3415.80 (the accidental
        # double) instead. The account-level number is the right one.
        #
        # So the derived figure is served ONLY where there is no final_pnl —
        # which is exactly the case it was built for: the closed portion of a
        # PARTIAL, which the reconciler does not price at all. Two numbers for
        # one fact on one row is the defect this platform keeps paying for.
        if row.final_pnl is None:
            item.derived_realised_pnl = derived.realised_pnl
            item.derived_realised_gross_pnl = derived.gross_pnl
            item.derived_realised_charges = derived.charges
            item.derived_realised_quantity = derived.quantity
            item.derived_realised_reason = derived.reason
        else:
            item.derived_realised_reason = (
                "priced from the account's trade book (final_pnl); the leg-level "
                "estimate is not shown because one row must carry one number"
            )

    # Attach the protective stop that lives at the BROKER.
    #
    # ``stop_loss_price`` is NULL on every direct-exit row: pine_replica owns
    # the trailing stop and re-places it at Dhan on each trail step without
    # telling this platform. The SL column therefore printed "—" over a live
    # short that had a real 3354.85 stop armed — an invisible stop reads as
    # no stop, which is the most dangerous thing this screen can imply.
    #
    # Read from cache only (the reconciliation poll fills it): a page load
    # must never make a broker call. An empty cache means UNKNOWN, so the
    # fields stay None and the UI keeps its dash — it never claims "no stop".
    try:
        stops = await broker_resting_stops.get_for_user(current_user.id)
    except Exception:
        logger.warning("positions.resting_stops_unavailable")
        stops = {}
    if stops:
        for item in items:
            # ONLY a position that is still in the market can be protected.
            # The lookup is by symbol, and this account recycles one contract
            # (BSE-SEP2026-FUT) across many rows — so without this guard the
            # OPEN short's stop was attached to every CLOSED row on the same
            # symbol too, advertising protection on positions that ended days
            # ago. Caught in end-to-end verification, 2026-09-09.
            if item.status not in ("open", "partial"):
                continue
            if item.remaining_quantity <= 0:
                continue
            found = stops.get(item.symbol.strip().upper())
            if not found:
                continue
            try:
                item.broker_stop_price = Decimal(str(found["price"]))
            except (InvalidOperation, KeyError, TypeError, ValueError):
                continue
            item.broker_stop_order_id = str(found.get("order_id") or "") or None

    return StrategyPositionListResponse(positions=items, count=len(items))


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def trigger_kill_switch(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> KillSwitchResponse:
    """Stop everything for this user: trip the switch, close, reject.

    This is Simple mode's "Sab band" button, and until 2026-09-06 it was a
    DIFFERENT brake from the one Pro reads. It closed the strategy engine's own
    positions and rejected in-flight signals, but never flipped the platform
    gate, so ``GET /api/kill-switch/status`` still answered ACTIVE. A customer
    tapped "Sab band", was told "Sab band ho gaya", switched to Pro and read
    "Chalu hai — naye signals par order ja sakte hain". Two brakes, one pedal.

    Side effects, in this order:
        * The platform kill-switch gate is flipped to TRIPPED **first**, so a
          webhook arriving mid-close is already rejected. This mirrors the
          ordering in ``KillSwitchService.check_and_trigger``.
        * Every ``open`` / ``partial`` :class:`StrategyPosition` row gets
          a closing ``StrategyExecution`` and is marked ``closed``.
        * Every ``received`` / ``validating`` :class:`StrategySignal` is
          flipped to ``rejected`` with a kill-switch note.
        * A :class:`KillSwitchEvent` row is written so ``/kill-switch/history``
          shows it and ``manual_reset`` has a row to close.

    Deliberately NOT done here: the broker-level emergency square-off chain
    (``_execute_emergency_square_off``). Pro's ``POST /kill-switch/trip`` gates
    that chain behind a confirmation token precisely because it once wiped
    personal Dhan positions alongside system ones (see the Layer 1 comment in
    kill_switch_service.py). "Sab band" is a single unconfirmed tap, so it
    stops what this engine owns and flips the gate — it does not reach into
    the broker. Adding that here would make the one-tap button more dangerous
    than the token-gated one.

    Idempotent — re-calling on a clean state returns 0/0 and writes no second
    event.
    """
    # 0. Flip the gate FIRST so a concurrent webhook rejects while we close.
    already_tripped = (
        await redis_client.get_kill_switch_status(current_user.id)
        == redis_client.KILL_SWITCH_TRIPPED
    )
    await redis_client.set_kill_switch_status(
        current_user.id, redis_client.KILL_SWITCH_TRIPPED
    )
    # 1. Close open positions
    # ⛔ NO TRACKING CUT-OFF HERE. DELIBERATELY. ⛔
    # This select is 90 lines from the reporting one above and looks almost
    # identical, which is exactly why this comment exists. The brake must close
    # EVERY open position the user holds, whatever its age. Filtering by the
    # record's start date would leave a real open Dhan position that "Sab band"
    # silently skips — and the endpoint would still answer success, because it
    # reports the count it closed, not the count it should have.
    # See app/core/tracking_epoch.py; the isolation test pins this.
    pos_stmt = select(StrategyPosition).where(
        StrategyPosition.user_id == current_user.id,
        StrategyPosition.status.in_(("open", "partial")),
    )
    positions = (await db.execute(pos_stmt)).scalars().all()
    for pos in positions:
        await close_position_now(
            db, position=pos, reason="kill_switch", ltp=None
        )

    # 2. Reject in-flight signals
    sig_stmt = (
        update(StrategySignal)
        .where(
            StrategySignal.user_id == current_user.id,
            StrategySignal.status.in_(("received", "validating")),
        )
        .values(
            status="rejected",
            notes="kill switch invoked",
            processed_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    sig_result = await db.execute(sig_stmt)
    rejected_count = sig_result.rowcount or 0

    # 3. Record the trip so Pro's status, history and reset all see ONE fact.
    #    Guarded on `already_tripped` to keep the endpoint idempotent: tapping
    #    "Sab band" twice must not stack events for one brake.
    if not already_tripped:
        daily_pnl = await pnl_service.calculate_daily_pnl(current_user.id, session=db)
        event = KillSwitchEvent(
            user_id=current_user.id,
            reason=TripReason.MANUAL.value,
            daily_pnl_at_trigger=daily_pnl,
            positions_squared_off=[
                {"position_id": str(p.id), "symbol": p.symbol} for p in positions
            ],
        )
        db.add(event)
        await db.flush()
        await redis_client.cache_set_json(
            _trip_meta_key(current_user.id),
            {
                "tripped_at": datetime.now(UTC).isoformat(),
                "reason": TripReason.MANUAL.value,
                "event_id": str(event.id),
            },
            ttl_seconds=_TRIP_META_TTL,
        )

    await db.commit()

    logger.info(
        "strategy_positions.kill_switch_triggered",
        user_id=str(current_user.id),
        positions_closed=len(positions),
        signals_rejected=rejected_count,
        gate_tripped=True,
        already_tripped=already_tripped,
    )

    return KillSwitchResponse(
        positions_closed=len(positions),
        signals_rejected=rejected_count,
        message=(
            f"Closed {len(positions)} position(s); rejected "
            f"{rejected_count} pending signal(s)."
        ),
    )


__all__ = [
    "DerivedFigures",
    "PositionLeg",
    "derive_position_figures",
    "router",
]
