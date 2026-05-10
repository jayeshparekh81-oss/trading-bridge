"""Position state — immutable snapshot + transitions.

Tracks the consolidated state of an open position for one strategy /
symbol / side. Every state-changing operation returns a **new**
:class:`PositionState`; the input is never mutated. The runner (Phase 3)
chains transitions to drive the position lifecycle:

    open_position(...)
        -> update_on_candle(...)            # high-watermark + trail update
        -> apply_partial_exit(...)          # 50 % off the table at target 1
        -> update_on_candle(...)
        -> close_position(...)              # full exit on stop / target / time

The trailing-stop update fires on candle close — locked Phase 2 edge-case
decision. Highest/lowest watermarks track candle highs/lows so the next
candle's exit engine sees a fully-updated position.

Output of a transition is always a fresh ``PositionState`` plus a
:class:`PartialExitRecord` (``apply_partial_exit`` only) or ``None``
(other transitions). Returning a tuple keeps engines stateless and easy
to test.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import Side


class PartialExitRecord(BaseModel):
    """Audit row for one partial exit. Frozen so it's hash- and serialise-safe."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    qty_percent: float = Field(..., gt=0, le=100)
    price: float = Field(..., gt=0)
    timestamp: datetime
    reason: str = Field(..., min_length=1, max_length=128)


class PositionState(BaseModel):
    """Immutable snapshot of an open position.

    ``trailing_stop_price`` is ``None`` while the position has no trail
    configured *or* has not yet pushed the trail above the entry stop.
    The exit engine treats ``None`` as "no trail trigger this bar".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_open: bool = True
    side: Side
    entry_price: float = Field(..., gt=0)
    entry_time: datetime
    quantity: float = Field(..., gt=0)
    remaining_quantity: float = Field(..., ge=0)
    highest_price_since_entry: float = Field(..., gt=0)
    lowest_price_since_entry: float = Field(..., gt=0)
    trailing_stop_price: float | None = Field(default=None, gt=0)
    partial_exits_done: tuple[PartialExitRecord, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_invariants(self) -> PositionState:
        if self.remaining_quantity > self.quantity:
            raise ValueError(
                f"remaining_quantity ({self.remaining_quantity}) cannot exceed "
                f"quantity ({self.quantity})."
            )
        if self.lowest_price_since_entry > self.highest_price_since_entry:
            raise ValueError(
                f"lowest_price_since_entry ({self.lowest_price_since_entry}) "
                f"cannot exceed highest_price_since_entry "
                f"({self.highest_price_since_entry})."
            )
        if not self.is_open and self.remaining_quantity != 0:
            raise ValueError("is_open=False requires remaining_quantity == 0.")
        return self


# ─── Transitions ────────────────────────────────────────────────────────


def open_position(
    *,
    side: Side,
    entry_price: float,
    quantity: float,
    entry_time: datetime,
) -> PositionState:
    """Build the initial :class:`PositionState` for a fresh entry.

    Highest / lowest watermarks seed at ``entry_price`` so the very next
    candle's update establishes a real range. ``trailing_stop_price``
    is ``None`` until the strategy's ``trailing_stop_percent`` puts a
    trail value above (BUY) / below (SELL) the entry.
    """
    if entry_price <= 0:
        raise ValueError(f"entry_price must be > 0; got {entry_price}.")
    if quantity <= 0:
        raise ValueError(f"quantity must be > 0; got {quantity}.")

    return PositionState(
        is_open=True,
        side=side,
        entry_price=entry_price,
        entry_time=entry_time,
        quantity=quantity,
        remaining_quantity=quantity,
        highest_price_since_entry=entry_price,
        lowest_price_since_entry=entry_price,
        trailing_stop_price=None,
        partial_exits_done=(),
    )


def update_on_candle(
    position: PositionState,
    candle: Candle,
    *,
    trailing_stop_percent: float | None = None,
) -> PositionState:
    """Apply candle-close updates: watermarks + trailing-stop ratchet.

    Trail rules (decision: updates AFTER candle close, not intra-bar):
      * BUY  side — trail = highest_seen * (1 - pct/100); never decreases.
      * SELL side — trail = lowest_seen  * (1 + pct/100); never increases.

    No-op when ``position.is_open`` is False (closed positions are inert).
    """
    if not position.is_open:
        return position

    new_high = max(position.highest_price_since_entry, candle.high)
    new_low = min(position.lowest_price_since_entry, candle.low)

    new_trail = position.trailing_stop_price
    if trailing_stop_percent is not None and trailing_stop_percent > 0:
        new_trail = _ratchet_trail(
            side=position.side,
            current_trail=position.trailing_stop_price,
            high=new_high,
            low=new_low,
            trailing_pct=trailing_stop_percent,
        )

    return position.model_copy(
        update={
            "highest_price_since_entry": new_high,
            "lowest_price_since_entry": new_low,
            "trailing_stop_price": new_trail,
        }
    )


def apply_partial_exit(
    position: PositionState,
    *,
    qty_percent: float,
    price: float,
    timestamp: datetime,
    reason: str,
) -> tuple[PositionState, PartialExitRecord]:
    """Reduce ``remaining_quantity`` by ``qty_percent`` of the original ``quantity``.

    Returns the new state and the audit record. Raises ``ValueError`` if
    the partial would over-exit the remaining quantity (caller should
    have called :func:`close_position` instead).
    """
    if not position.is_open:
        raise ValueError("Cannot apply partial exit to a closed position.")
    if qty_percent <= 0 or qty_percent > 100:
        raise ValueError(f"qty_percent must be in (0, 100]; got {qty_percent}.")
    if price <= 0:
        raise ValueError(f"price must be > 0; got {price}.")

    qty_to_close = position.quantity * (qty_percent / 100.0)
    new_remaining = position.remaining_quantity - qty_to_close
    # Numerical-noise tolerance so a strictly-equal partial-to-100 % path
    # doesn't trip the over-exit check; clamp tiny negatives to zero.
    if new_remaining < -1e-9:
        raise ValueError(
            f"Partial exit of {qty_percent}% would over-exit remaining "
            f"{position.remaining_quantity} (qty_to_close={qty_to_close})."
        )
    new_remaining = max(0.0, new_remaining)

    record = PartialExitRecord(
        qty_percent=qty_percent,
        price=price,
        timestamp=timestamp,
        reason=reason,
    )
    new_state = position.model_copy(
        update={
            "remaining_quantity": new_remaining,
            "partial_exits_done": (*position.partial_exits_done, record),
            "is_open": new_remaining > 0,
        }
    )
    return new_state, record


def close_position(position: PositionState) -> PositionState:
    """Mark the position fully closed. Idempotent if already closed."""
    if not position.is_open:
        return position
    return position.model_copy(update={"is_open": False, "remaining_quantity": 0.0})


# ─── Helpers ────────────────────────────────────────────────────────────


def _ratchet_trail(
    *,
    side: Side,
    current_trail: float | None,
    high: float,
    low: float,
    trailing_pct: float,
) -> float | None:
    """Compute the new trailing-stop price under the locked ratchet rule.

    The trail moves only in the position's favour:
      * BUY: candidate = high * (1 - pct/100); accept if > current_trail.
      * SELL: candidate = low * (1 + pct/100); accept if < current_trail.

    First call (``current_trail is None``) seeds the trail unconditionally.
    """
    factor = trailing_pct / 100.0
    if side is Side.BUY:
        candidate = high * (1.0 - factor)
        if current_trail is None or candidate > current_trail:
            return candidate
        return current_trail

    # SELL side
    candidate = low * (1.0 + factor)
    if current_trail is None or candidate < current_trail:
        return candidate
    return current_trail


__all__ = [
    "PartialExitRecord",
    "PositionState",
    "apply_partial_exit",
    "close_position",
    "open_position",
    "update_on_candle",
]
