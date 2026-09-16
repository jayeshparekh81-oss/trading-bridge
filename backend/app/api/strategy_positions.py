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
from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text, update
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
from app.schemas.kill_switch import TripReason
from app.schemas.strategy_position import (
    DuplicateExitRead,
    KillSwitchResponse,
    PositionLegRead,
    StrategyPositionListResponse,
    StrategyPositionRead,
)
from app.services import broker_resting_stops, pnl_service

# The trip-meta key helper lives in the kill-switch service. It is imported,
# never modified — app/api/kill_switch.py:manual_trip already imports
# ``_reset_token_key`` from the same module, so this is the established way to
# share the key shape rather than re-spelling it here and letting the two drift.
from app.services.kill_switch_service import _TRIP_META_TTL, _trip_meta_key
from app.services.owner_executions import PRICED_ATTRIBUTION_TAGS as _PRICED_TAGS
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
    #: Display-only, never used in pricing. ``None`` when not recorded.
    side: str | None = None
    filled_at: str | None = None


@dataclass(frozen=True)
class DerivedFigures:
    """What the row can honestly say about its own exit, and why."""

    exit_price: Decimal | None
    realised_pnl: Decimal | None  # net of what DHAN BILLED; None if unbilled
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
    billed_charges: dict[str, Decimal] | None = None,
) -> DerivedFigures:
    """Derive the exit price and the realised P&L on the CLOSED portion.

    Rules, all of them the founder's:

    * The exit price is the quantity-weighted mean of the close legs. If ANY
      close leg is unpriced, or the close quantities do not add up to the
      quantity that actually left the position, NOTHING is returned — a mean
      over the resolvable subset would be a guess dressed as a fact.
    * The realised figure prices the closed portion, including the closed part
      of a PARTIAL. It is NET of what DHAN BILLED — never of a model.
    * 🔴 NET IS BILLED OR IT IS NULL (founder's ruling, 2026-09-16). This used
      to subtract an estimated Indian F&O charge stack, which is a modelled
      number on a page shown to other people. It was measurably wrong: across
      1..16 Sep the model was optimistic by 1,029.84, and it cannot be repaired
      — on 04-Sep it charges STT on BOTH 400-lot sells while Dhan billed
      1366.40 on one and 0.00 on the other. No per-fill formula can reproduce
      that bill at any level of care.
      So when every leg's billed charge is known, net = gross - billed. When
      any is missing, GROSS is still shown, charges read "baaki" and net is
      NULL. There is no fallback.
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

    # Turnover is no longer computed here: it existed only to feed the cost
    # model, and net now comes from Dhan's own bill.
    if direction == "buy":  # long: bought to open, sold to close
        gross = exit_value - entry_price * closed_qty
    else:  # short: sold to open, bought to close
        gross = entry_price * closed_qty - exit_value

    gross_q = _q(gross, _Q2)

    # WHAT DHAN BILLED on the orders behind these legs. A missing entry is not
    # a zero: an unbilled fill that counted as costing nothing would flatter
    # every net on the page, every day, until settlement caught up.
    billed = billed_charges or {}
    leg_orders = {
        leg.broker_order_id
        for leg in (*entry_legs, *exit_legs)
        if leg.broker_order_id
    }
    unbilled = sorted(o for o in leg_orders if o not in billed)
    charges_total = (
        None if unbilled else sum((billed[o] for o in leg_orders), Decimal("0"))
    )
    net = None if charges_total is None else _q(gross_q - charges_total, _Q2)

    portion = (
        f"the closed {closed_qty} of {total_quantity}"
        if closed_qty != int(total_quantity or 0)
        else f"all {closed_qty}"
    )
    # Every leg reaching here IS a broker fill — the unfilled guard above
    # returned otherwise — so the figure is fill-sourced by construction.
    reason = (
        f"derived from the bot's own legs on {portion}: entry "
        f"{_q(entry_price, _Q4)}, exit {exit_price}; "
    )
    if charges_total is None:
        reason += (
            f"charges Dhan ke bill se BAAKI on {len(unbilled)} order(s) "
            f"({', '.join(unbilled[:3])}) — gross dikhaya hai, net baaki hai"
        )
    else:
        reason += f"charges {_q(charges_total, _Q2)} Dhan ke bill se"
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
        charges=charges_total,
        quantity=closed_qty,
        reason=reason,
    )


#: ``leg_role`` for the engine's OWN broker-side stop fill. pine_replica places
#: a Forever/GTT order straight at Dhan, so when it fires there is no platform
#: order and no ``strategy_executions`` row — but it is the bot's exit and the
#: position cannot be priced without it.
_BROKER_STOP_ROLE = "broker_stop"

#: ``leg_role`` for a platform exit that fired against a position the broker had
#: ALREADY closed. Not this position's exit — its own separate round trip.
_DUPLICATE_EXIT_ROLE = "duplicate_exit"

#: ``leg_role`` for a close taken by a MANUAL Dhan-app order. It IS a real
#: broker fill with a real order id — but the founder's rule of 2026-09-16 says
#: a manual fill between a position's entry and its close leaves the P&L NULL,
#: so it is deliberately carried unpriced. The row then says who closed it and
#: that the trade is not counted, which is a different statement from "no fill
#: exists" and the only honest one here.
_MANUAL_CLOSE_ROLE = "manual_close"


#: What each leg is CALLED on the page, in the customer's own words. The
#: engine's broker-side stop is the one that needed a name: it is the bot's own
#: exit, taken at the broker, and calling it anything vaguer invites the reader
#: to think a human did it.
LEG_LABELS: dict[str, str] = {
    "entry": "entry",
    "direct_partial": "partial",
    "direct_exit": "exit",
    "direct_sl": "SL / trailing exit",
    "partial_target": "partial (target)",
    "trailing_sl": "trailing SL",
    "hard_sl": "hard SL",
    "kill_switch": "kill switch",
    _BROKER_STOP_ROLE: "broker stop (auto)",
    _MANUAL_CLOSE_ROLE: "manual close (Dhan app)",
    _OPERATOR_RECONCILE_ROLE: "operator close (no fill)",
}


#: IST. Every time a customer reads on these pages is this timezone — the
#: founder trades IST and the broker reports IST.
_IST = timezone(timedelta(hours=5, minutes=30))


def ist_display(value: Any) -> str | None:
    """An instant as the founder reads it: ``04/09/26, 01:11 pm``.

    🔴 R1.1. The C5 render printed ``2026-09-04T07:41:13`` for the broker stop —
    the raw UTC instant — beside rows showing local time. Two clocks on one
    page is worse than either alone: the reader cannot tell which rows to
    trust, and the engine stop looked like it fired at 7am.

    Formatted HERE, server-side, deliberately. The alternative — each surface
    formatting for itself — is how the text render and the React page drift
    apart, and this exact field already drifted once. The raw instant is still
    served alongside (``filled_at``) for anything that needs to compute.
    """
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(value, datetime):
        parsed = value
    else:
        return None
    # A naive stamp is UTC by this platform's convention (every stored
    # timestamp is tz-aware UTC; the tape writes offsets explicitly).
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    local = parsed.astimezone(_IST)
    return local.strftime("%d/%m/%y, %I:%M %p").replace("AM", "am").replace("PM", "pm")


def price_display(value: Any) -> str | None:
    """A price at two decimals, for the screen only.

    R1.4. The record holds what Dhan actually filled — the 08-Sep engine stop
    was 3394.025 — and that third decimal must survive in the DATA, because a
    leg rounded at the source stops reconciling against the broker. But a money
    column printing a different number of decimals per row reads as sloppiness
    on a page shown to other people.

    So: round for the eye, keep the record intact. ROUND_HALF_UP because that
    is what a reader checking the arithmetic by hand will do — banker's
    rounding would send 3394.025 DOWN to 3394.02 and look like an error to
    everyone who has not heard of it.

    Returns None for a leg with no fill of its own, so the page prints a dash
    rather than a confident 0.00.
    """
    if value is None:
        return None
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (ArithmeticError, TypeError, ValueError):
        return None


def leg_label(leg_role: str) -> str:
    """Never invent a name — an unmapped role prints as itself."""
    return LEG_LABELS.get(leg_role.strip().lower(), leg_role)



def manual_close_note(history: Any) -> str | None:
    """The founder's own sentence for a position a manual order closed.

    Wording is his, verbatim (2026-09-16 review): the page must NOT say "no
    broker fill". A fill exists — order 35226091145606, BUY 200 @3215.40 on
    11-09 at 09:31 — it is simply a Dhan-app order, and by his rule this
    trade's P&L is not counted. Saying "no broker fill" would be false about
    the broker AND would read as our data being missing rather than his rule
    being applied.
    """
    for event in history or []:
        if not isinstance(event, dict):
            continue
        if str(event.get("leg_role") or "").strip().lower() != _MANUAL_CLOSE_ROLE:
            continue
        qty = event.get("qty")
        order_id = str(event.get("broker_order_id") or "").strip()
        price = event.get("price")
        side = str(event.get("side") or "").strip().upper()
        when = str(event.get("ts_ist") or "").strip()
        if qty is None or not order_id or price is None:
            continue
        return (
            f"{qty} manual Dhan-app order se band ({order_id}, {side} {qty} "
            f"@{price}, {when}) — is trade ka P&L nahi gina"
        )
    return None


#: Verdicts under which a stored truth-check run AGREED with Dhan. "attention"
#: counts: on a day the founder traded by hand, our record still matched the
#: broker — the manual trade is his business, not a defect in ours.
_AGREEING_VERDICTS = ("green", "attention")


async def billed_charges_by_order(
    session: AsyncSession, order_ids: set[str]
) -> dict[str, Decimal]:
    """What Dhan BILLED, per broker order, from the ingested record.

    🔴 THE FOUNDER'S RULING, 2026-09-16: net is what Dhan billed, never what a
    model says. This page used to subtract an estimated Indian F&O charge stack
    — a modelled number shown to other people as the bot's record. Measured
    across 1..16 Sep, that model was optimistic by 1,029.84, and it cannot be
    fixed: on 04-Sep it charges STT on BOTH 400-lot sells while Dhan billed
    1366.40 on one and 0.00 on the other.

    An order with no billed charge is simply ABSENT from this map. It must
    never be read as zero — an unbilled fill counted as free would flatter
    every net on the page, every day, until settlement caught up.

    Fails closed: no table (migration 048 not applied) ⇒ empty map ⇒ every row
    shows GROSS with charges "baaki" and net NULL. Never a modelled fallback.
    """
    if not order_ids:
        return {}
    try:
        rows = (
            await session.execute(
                text(
                    "SELECT broker_order_id, billed_charges "
                    "FROM broker_fill_provenance "
                    "WHERE broker_order_id = ANY(:ids) AND billed_charges IS NOT NULL"
                ),
                {"ids": list(order_ids)},
            )
        ).all()
    except Exception:
        logger.warning("positions.billed_charges_unavailable")
        return {}
    return {str(r[0]): Decimal(str(r[1])) for r in rows if r[1] is not None}


async def covering_truth_runs(
    session: AsyncSession, closed_ats: list[datetime]
) -> dict[datetime, str]:
    """For each close time, the IST date of a stored run that covers it.

    🔴 R1.2. THE BADGE MUST BE EARNED. "Dhan se verified ✅" previously meant
    only that a final_pnl existed and its tag was priced — i.e. that WE had
    done a sum, not that anyone had compared it with Dhan. A badge with no
    stored run behind it is the same class of claim as a modelled number
    labelled as billed.

    So the badge now requires a row in ``truth_check_runs`` whose window
    contains the position's close AND whose verdict agreed with the broker,
    and it shows THAT RUN'S DATE — so it can never outlive the check that
    earned it.

    Fails closed in every direction: no table, no run, a red run, or a close
    time we do not have ⇒ no badge. "Verify baaki" is always safe to say; a
    false ✅ is not.
    """
    if not closed_ats:
        return {}
    try:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT window_start, window_end, ran_at, verdict
                      FROM truth_check_runs
                     WHERE verdict = ANY(:ok)
                     ORDER BY ran_at DESC
                    """
                ),
                {"ok": list(_AGREEING_VERDICTS)},
            )
        ).mappings().all()
    except Exception:
        # The table may not exist yet (migration 048 not applied). A missing
        # check is "verify baaki", never a silent ✅.
        logger.warning("positions.truth_check_runs_unavailable")
        return {}

    out: dict[datetime, str] = {}
    for closed_at in closed_ats:
        if closed_at is None:
            continue
        when = closed_at if closed_at.tzinfo else closed_at.replace(tzinfo=UTC)
        for run in rows:
            start, end = run["window_start"], run["window_end"]
            if start is None or end is None:
                continue
            if start <= when <= end:
                ran = run["ran_at"]
                out[closed_at] = ran.astimezone(_IST).date().isoformat()
                break
    return out


def _history_legs(history: Any) -> list[PositionLeg]:
    """Legs a position has that ``strategy_executions`` cannot hold.

    🔴 ATTRIBUTED THROUGH THE ENGINE LEDGER, NEVER BY TIME.

    Two kinds, both written by the one-off reconcile run (never at request
    time, and never by a recurring broker poll — the live account's Dhan quota
    belongs to the trading engine):

    * ``broker_stop`` — the engine's own Forever/GTT stop child. It IS the
      bot's exit: on 2026-09-04 order ``312260904412406`` SELL 400 @3415.50
      took the 03-Sep position to zero, and on 2026-09-08 order
      ``312260908126806`` SELL 800 @3394.025 closed the 07-Sep one. Neither has
      a platform row, because ``signal_id`` is NOT NULL with an FK to
      ``strategy_signals`` and the only writer of a signal is the webhook.

      The chain that attributes one, every hop a recorded id: the child fill's
      ``algoOrdNo`` in the engine's order tape gives the parent Forever id; the
      engine's own placement line gives which trade that parent was placed for;
      ``own_fills.json`` gives that trade's entry order id, which is the
      ``broker_order_id`` already on our entry legs. No timestamp is compared.

    * ``operator_reconcile`` — a quantity a human recorded as closed with NO
      order behind it. Carried with ``price=None`` on purpose, so the row
      becomes unpriceable and says why. Never the recorded price: the founder's
      rule is that every P&L comes from an actual Dhan fill, and an estimate
      here published 3287.65 / 41,769.71 for three weeks while the real fill
      sat in the trade book unlooked-at.

    A ``duplicate_exit`` entry is NOT returned — it is a different round trip
    and is read separately by :func:`duplicate_exit_of`.
    """
    out: list[PositionLeg] = []
    for event in history or []:
        if not isinstance(event, dict):
            continue
        role = str(event.get("leg_role") or "").strip().lower()
        if role not in (_OPERATOR_RECONCILE_ROLE, _BROKER_STOP_ROLE, _MANUAL_CLOSE_ROLE):
            continue
        try:
            qty = int(event.get("qty"))
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue

        if role == _BROKER_STOP_ROLE:
            # A real fill. It must carry BOTH a price and the broker's own
            # order id, or it is not evidence and is skipped rather than
            # half-trusted.
            order_id = str(event.get("broker_order_id") or "").strip()
            raw_price = event.get("price")
            if not order_id or raw_price is None:
                continue
            try:
                price = Decimal(str(raw_price))
            except (ArithmeticError, TypeError, ValueError):
                continue
            out.append(
                PositionLeg(
                    leg_role=_BROKER_STOP_ROLE,
                    quantity=qty,
                    price=price,
                    broker_order_id=order_id,
                    broker_fill=True,
                    side=str(event.get("side") or "") or None,
                    filled_at=str(event.get("ts") or "") or None,
                )
            )
            continue

        if role == _MANUAL_CLOSE_ROLE:
            # A REAL fill, carried UNPRICED on purpose. The founder's rule
            # leaves the trade's P&L NULL; the order id rides along so the row
            # can name who closed it instead of implying the fill is missing.
            out.append(
                PositionLeg(
                    leg_role=_MANUAL_CLOSE_ROLE,
                    quantity=qty,
                    price=None,
                    broker_order_id=str(event.get("broker_order_id") or "") or None,
                    broker_fill=False,
                    side=str(event.get("side") or "") or None,
                    filled_at=str(event.get("ts") or "") or None,
                )
            )
            continue

        if event.get("broker_fill") is not False:
            continue
        out.append(
            PositionLeg(
                leg_role=_OPERATOR_RECONCILE_ROLE,
                quantity=qty,
                price=None,
                broker_order_id=None,
                broker_fill=False,
            )
        )
    return out


def duplicate_exit_of(history: Any) -> dict[str, Any] | None:
    """The platform exit that fired against an ALREADY-CLOSED position.

    🔴 2026-09-04, and it is shown, not hidden. At 13:11:13 the engine's stop
    closed the 03-Sep position. At 13:15:12 the platform's own SL_HIT sold
    another 400 — the engine's own post-mortem (``closing_guard.py``) records
    that this "OPENED A SHORT 400 FROM FLAT". Two manual buys closed it at
    13:34 for a realised loss.

    That loss is the system's mistake, not the strategy's, so it is NOT folded
    into the position's P&L — but the founder's rule is that it appears on the
    page with its own number and counts in the page total. A bug that cost
    money is part of the record.
    """
    for event in history or []:
        if not isinstance(event, dict):
            continue
        if str(event.get("leg_role") or "").strip().lower() == _DUPLICATE_EXIT_ROLE:
            return event
    return None


def duplicate_exit_orders(event: dict[str, Any] | None) -> set[str]:
    """Every broker order this mistake touched: the accidental exit AND the
    fills that closed the position it opened.

    All of them were BILLED. Charging the page only for the accidental sell
    would understate the cost of the system's own error.
    """
    if not event:
        return set()
    orders: set[str] = set()
    if event.get("broker_order_id"):
        orders.add(str(event["broker_order_id"]))
    for closer in event.get("closed_by") or []:
        if isinstance(closer, dict) and closer.get("broker_order_id"):
            orders.add(str(closer["broker_order_id"]))
    return orders


def price_duplicate_exit(
    event: dict[str, Any] | None, billed: dict[str, Decimal]
) -> dict[str, Any] | None:
    """Add Dhan's billed charges and the resulting net to the duplicate exit.

    🔴 CAUGHT BY THE R4 RENDER, not by reading the code. The page summed this
    row's GROSS into a NET total, and the headline came out 133.13 too high —
    because the accidental sell and its two closing buys were billed like any
    other trade. A bug that cost money costs charges too.

    Fails closed: if ANY of the orders has no bill, both figures are None and
    the page's total says "baaki" rather than counting this one at gross.
    """
    if not event:
        return None
    priced = dict(event)
    orders = duplicate_exit_orders(event)
    missing = [o for o in orders if o not in billed]
    charges = None if (missing or not orders) else sum(
        (billed[o] for o in orders), Decimal("0")
    )
    priced["billed_charges"] = charges
    gross = event.get("gross_pnl")
    priced["net_pnl"] = (
        None if charges is None or gross is None else Decimal(str(gross)) - charges
    )
    return priced


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
        # The leg's own fill time. The page prints a time against every leg —
        # a price with no time is a number the reader cannot place against the
        # broker's own statement.
        StrategyExecution.placed_at,
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
    for sid, leg_role, quantity, price, broker_order_id, placed_at in await db.execute(stmt):
        out.setdefault(sid, []).append(
            PositionLeg(
                leg_role=str(leg_role or ""),
                quantity=int(quantity or 0),
                price=price,
                broker_order_id=broker_order_id or None,
                filled_at=placed_at.isoformat() if placed_at is not None else None,
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
    # R1.2. ONE query for the whole page, same discipline as the legs lookup:
    # which closes are covered by a stored truth-check run that agreed with
    # Dhan. No run ⇒ no badge.
    verified_dates = await covering_truth_runs(
        db, [r.closed_at for r in rows if r.closed_at is not None]
    )
    # D. ONE query for the page's billed charges. Net is billed or it is NULL.
    all_leg_orders = {
        leg.broker_order_id
        for legs_for_sig in legs_map.values()
        for leg in legs_for_sig
        if leg.broker_order_id
    }
    for r in rows:
        for leg in _history_legs(r.action_history):
            if leg.broker_order_id:
                all_leg_orders.add(leg.broker_order_id)
        # The duplicate exit's own orders too — the accidental sell AND the
        # fills that closed the position it opened were all billed.
        all_leg_orders |= duplicate_exit_orders(duplicate_exit_of(r.action_history))
    billed_map = await billed_charges_by_order(db, all_leg_orders)
    for item, row, sig_ids in zip(items, rows, history_by_row, strict=True):
        legs: list[PositionLeg] = []
        for sid in sig_ids:
            legs.extend(legs_map.get(sid, ()))
        # Engine broker-stop fills (real, priced) and operator-recorded
        # quantities (unpriced), attributed through the engine ledger. In
        # memory only — never a strategy_executions row. See _history_legs.
        legs.extend(_history_legs(row.action_history))

        # 🔴 A DUPLICATE EXIT IS NOT THIS POSITION'S EXIT.
        # On 2026-09-04 the platform's SL_HIT fired 4 minutes after the engine's
        # stop had already closed the position, and opened a short from flat.
        # Its execution row is real and stays in the orders log, but counting it
        # as an exit leg here prices the position against a fill that belongs to
        # a different round trip — which is exactly how 844b8037 came to carry
        # 3415.80 instead of 3415.50. Excluded by ORDER ID, from the record the
        # reconcile run wrote; never by time.
        dup = duplicate_exit_of(row.action_history)
        if dup is not None:
            dup_order = str(dup.get("broker_order_id") or "").strip()
            if dup_order:
                legs = [leg for leg in legs if leg.broker_order_id != dup_order]
            item.duplicate_exit = DuplicateExitRead.model_validate(
                price_duplicate_exit(dup, billed_map)
            )

        derived = derive_position_figures(
            side=row.side,
            total_quantity=row.total_quantity,
            remaining_quantity=row.remaining_quantity,
            legs=legs,
            pnl_attribution=row.pnl_attribution,
            billed_charges=billed_map,
        )
        item.legs = [
            PositionLegRead(
                leg_role=leg.leg_role,
                label=leg_label(leg.leg_role),
                side=leg.side,
                quantity=leg.quantity,
                price=leg.price,
                price_display=price_display(leg.price),
                broker_order_id=leg.broker_order_id,
                filled_at=leg.filled_at,
                filled_at_ist=ist_display(leg.filled_at),
                broker_fill=leg.broker_fill,
            )
            for leg in legs
        ]
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
        # S1(d): the legs must add up, or the row says so in the customer's own
        # words. ``derive_position_figures`` already refuses to price an
        # unbalanced row; this promotes that refusal to a field the page can
        # render as a label instead of leaving a silent blank.
        item.derived_gross_pnl = derived.gross_pnl
        # "Dhan se verified" means exactly one thing: this row's money came out
        # of a trade-book reconcile. That is the only state in which both a
        # priced attribution tag AND a stored final_pnl exist — the live path
        # writes neither. Anything else is "verify baaki", including a row we
        # simply have not got to yet.
        item.dhan_verified = (
            row.final_pnl is not None and row.pnl_attribution in _PRICED_TAGS
        )
        # R1.2 / R1.3 — the badge now has three honest states instead of a
        # boolean that conflated "we have not checked" with "there is nothing
        # to check".
        manual_note = manual_close_note(row.action_history)
        if manual_note is not None:
            # R1.3. A hand-closed position is not awaiting verification — it
            # has its answer. Showing "Dhan se verify baaki" here would promise
            # a ✅ that can never arrive, because by the founder's own rule this
            # trade's P&L is not counted at all.
            item.verification = "manual_closed"
        elif item.dhan_verified and row.closed_at is not None:
            run_date = verified_dates.get(row.closed_at)
            if run_date is not None:
                item.verification = "verified"
                item.verified_on = run_date
        item.legs_balanced = derived.quantity is not None or row.status != "closed"
        if not item.legs_balanced:
            # A manual close gets the founder's own wording; anything else gets
            # the derivation's reason.
            item.incomplete_reason = manual_close_note(row.action_history) or derived.reason
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
