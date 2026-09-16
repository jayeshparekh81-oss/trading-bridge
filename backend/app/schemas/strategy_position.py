"""Pydantic schemas for ``strategy_positions`` — list API output + kill switch."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PositionLegRead(BaseModel):
    """One leg of a position, as the page prints it.

    C2 (2026-09-16). ``/positions`` showed a position's numbers but never its
    LEGS, so "entry 3270, exit 3370.45" appeared with nothing behind it and the
    engine's own broker-stop fill — the thing that actually closed two of the
    trades — was invisible. This page is shown to other people; a P&L whose
    fills cannot be read off the screen is a number they have to take on trust.

    Every field here traces to a Dhan fill: the order id is the broker's own,
    and the price is its traded price. ``price`` is None ONLY for a leg that
    has no fill of its own to show (a manual close, whose P&L this record
    deliberately does not count).
    """

    model_config = ConfigDict(extra="ignore")

    #: entry | direct_partial | direct_exit | direct_sl | broker_stop | manual_close
    leg_role: str
    #: What the customer reads. "broker stop (auto)" for the engine's own stop.
    label: str
    side: str | None = None
    quantity: int
    #: FULL PRECISION, exactly as Dhan filled it. The 08-Sep engine stop really
    #: did fill at 3394.025, and this field keeps that third decimal — rounding
    #: at the source would make the leg stop reconciling against the broker.
    price: Decimal | None = None
    #: R1.4. The same price at TWO decimals, for the screen. Formatted here, not
    #: in the browser, so every surface (page, CSV, alert) shows one number and
    #: they cannot drift apart. Never used in arithmetic.
    price_display: str | None = None
    broker_order_id: str | None = None
    #: Broker fill time, ISO, as the broker reported it. None when not recorded.
    #: This is the INSTANT — for computing, sorting, reconciling.
    filled_at: str | None = None
    #: The same instant as the founder reads it: ``04/09/26, 01:11 pm``.
    #: Formatted once, server-side, so the text render and the page cannot
    #: show two different clocks for one fill (they did — R1.1).
    filled_at_ist: str | None = None
    #: False for a leg with no fill of its own (a manual close).
    broker_fill: bool = True


class DuplicateExitRead(BaseModel):
    """A platform exit that fired against a position the broker had ALREADY closed.

    🔴 2026-09-04. At 13:11:13 the engine's own Forever stop child
    (``312260904412406``, SELL 400 @3415.50) took the 03-Sep position to zero.
    At 13:15:12 the platform's SL_HIT sold another 400 @3415.80 — the engine's
    own post-mortem records that this "OPENED A SHORT 400 FROM FLAT". Two
    manual buys closed it at 13:34 @3426.70 for a realised loss.

    It is NOT folded into the position's P&L — it is a different round trip —
    but it is shown on the page with its own number and it COUNTS in the page
    total. The founder's rule: a bug that cost money is part of the record,
    shown exactly like a losing trade.
    """

    model_config = ConfigDict(extra="ignore")

    #: The platform order that should never have gone out.
    broker_order_id: str | None = None
    side: str | None = None
    qty: int | None = None
    price: Decimal | None = None
    #: The fills that closed the position it accidentally opened, with their
    #: own broker order ids — so every rupee below traces to a real fill.
    closed_by: list[dict[str, Any]] = Field(default_factory=list)
    #: Fill-sourced. NULL when the closing fills are not all known.
    gross_pnl: Decimal | None = None
    #: What the page prints beside it, in the customer's own words.
    label: str | None = None
    reason: str | None = None


class StrategyPositionRead(BaseModel):
    """Public read shape — used by GET /api/strategies/positions.

    ⛔ NO INTERNAL IDS, NO RAW BROKER PAYLOAD. ⛔
    ``broker_credential_id`` was here from the beginning and no surface ever
    rendered it: it names WHICH stored credential placed the order, which is
    our plumbing, not the customer's business. It went out with the raw Dhan
    envelope that was leaking from the executions endpoint (2026-09-10).
    A field nobody renders is a field that can only leak.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_id: uuid.UUID
    signal_id: uuid.UUID | None
    symbol: str
    side: str
    total_quantity: int
    remaining_quantity: int
    avg_entry_price: Decimal | None
    target_price: Decimal | None
    stop_loss_price: Decimal | None
    trail_offset: Decimal | None
    highest_price_seen: Decimal | None
    status: str
    opened_at: datetime
    closed_at: datetime | None
    final_pnl: Decimal | None
    #: ``bot_only`` | ``account_flat`` | ``human_interfered`` | ``unpriceable``
    #: | ``paper_sim`` | None (not yet attributed). A NULL ``final_pnl`` with
    #: ``human_interfered`` means "human-interfered — not attributable": the
    #: founder's manual fills on the same contract make the bot's exit price a
    #: guess, so nothing is published rather than a wrong number.
    pnl_attribution: str | None = None
    pnl_attribution_detail: str | None = None
    #: The protective stop resting at the BROKER, when one is cached.
    #: ``stop_loss_price`` above is OUR column and is NULL for every
    #: direct-exit row, because ``pine_replica`` places and re-places the
    #: trailing stop straight at Dhan and never tells this platform. The
    #: screen printed "—" while a real stop was armed. NULL here means
    #: UNKNOWN (not yet read), never "no stop" — the UI must not turn one
    #: into the other.
    broker_stop_price: Decimal | None = None
    broker_stop_order_id: str | None = None
    created_at: datetime

    # ─── HOW IT CLOSED (real columns, no migration) ──────────────────────
    #: ``strategy_positions.exit_reason`` — the leg role that finished the
    #: row (``direct_exit`` / ``direct_sl`` / ``direct_partial_full`` /
    #: ``kill_switch`` …). NULL while the position is still running.
    exit_reason: str | None = None
    #: ``last_action`` / ``last_action_at`` — the most recent event on the
    #: row (``entry`` | ``partial`` | ``exit`` | ``sl_hit``). Together with
    #: ``exit_reason`` this is the whole "how it closed" story the screen
    #: had to guess at before. Internal-exit strategies leave both NULL.
    last_action: str | None = None
    last_action_at: datetime | None = None

    # ─── DERIVED figures (computed per request, never stored) ────────────
    #: Quantity-weighted mean price of the position's EXIT legs, from
    #: ``strategy_executions``. There is no exit-price COLUMN — this is
    #: derived. NULL when the legs cannot be resolved (missing leg, unpriced
    #: leg, leg quantities that do not add up to the closed quantity); a
    #: partial mean over a subset of the exit would be a guess, so nothing
    #: is returned instead.
    exit_price: Decimal | None = None
    #: Realised P&L on the CLOSED PORTION only, derived from the bot's own
    #: entry/exit legs — NET of estimated charges. It is deliberately NOT
    #: ``final_pnl``: that column is written by the reconciler for
    #: ``status=closed`` rows only, and it is the account-level number.
    #: This one prices the closed quantity of a PARTIAL too, per the
    #: founder's rule that a human-interfered tag may apply to the
    #: ambiguous part while the unambiguous closed portion is still priced.
    derived_realised_pnl: Decimal | None = None
    #: The same figure BEFORE charges, and the estimated charges themselves,
    #: so the net is auditable on the row (Glass Box).
    derived_realised_gross_pnl: Decimal | None = None
    derived_realised_charges: Decimal | None = None
    #: The quantity the derived figure prices — i.e. the closed portion.
    derived_realised_quantity: int | None = None
    #: ALWAYS populated: the basis when the figure was computed, the reason
    #: when it is NULL. The founder's rule is that a row must say WHY, never
    #: a silent blank.
    derived_realised_reason: str | None = None
    #: S1(d). False when the position is CLOSED but its legs do not add up
    #: (quantity in != quantity out). The row then shows "incomplete" and the
    #: reason instead of a number — a P&L over legs that do not reconcile is a
    #: guess wearing a decimal point.
    legs_balanced: bool = True
    incomplete_reason: str | None = None
    #: Present only on a position whose exit was duplicated by a system fault.
    duplicate_exit: DuplicateExitRead | None = None
    #: Every leg behind this row, in order. Empty only when nothing is recorded.
    legs: list[PositionLegRead] = Field(default_factory=list)
    #: GROSS on the closed portion, fill-sourced. Served alongside the net
    #: figure so a page total can sum like-for-like instead of mixing the two —
    #: the mistake the 2026-09-16 review caught in the first S4 table.
    derived_gross_pnl: Decimal | None = None
    #: True when this row's money came from a Dhan trade-book reconcile.
    #: Kept for the production frontend, which already reads it (C4: response
    #: models may GAIN fields, never lose one). New pages should read
    #: ``verification`` instead — it distinguishes the three real states.
    dhan_verified: bool = False
    #: R1.2/R1.3. What this row's number has actually been checked against:
    #:
    #:   "verified"      a STORED truth-check run covers this position's close
    #:                   and that run agreed with Dhan. ``verified_on`` carries
    #:                   the run's date, so the badge can never outlive the
    #:                   check that earned it.
    #:   "manual_closed" a hand-placed Dhan-app order closed it. There is no
    #:                   P&L to verify — the row reads "manual se band". This is
    #:                   an ANSWER, not a pending state.
    #:   "pending"       nothing has checked it yet: "Dhan se verify baaki".
    #:
    #: A badge with no stored run behind it is the same class of claim as a
    #: modelled number labelled as billed, which is why "verified" is the only
    #: value that requires evidence.
    verification: str = "pending"
    #: The IST date of the truth-check run that verified this row. None unless
    #: ``verification == "verified"``.
    verified_on: str | None = None


class StrategyPositionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positions: list[StrategyPositionRead] = Field(default_factory=list)
    count: int = Field(..., ge=0)


class KillSwitchResponse(BaseModel):
    """Response from POST /api/strategies/kill-switch."""

    model_config = ConfigDict(extra="forbid")

    positions_closed: int = Field(..., ge=0)
    signals_rejected: int = Field(
        default=0,
        ge=0,
        description="Pending signals (status=received/validating) marked rejected.",
    )
    message: str


__all__ = [
    "DuplicateExitRead",
    "KillSwitchResponse",
    "PositionLegRead",
    "StrategyPositionListResponse",
    "StrategyPositionRead",
]
