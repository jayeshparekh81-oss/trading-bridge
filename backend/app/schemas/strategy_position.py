"""Pydantic schemas for ``strategy_positions`` — list API output + kill switch."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
    "KillSwitchResponse",
    "StrategyPositionListResponse",
    "StrategyPositionRead",
]
