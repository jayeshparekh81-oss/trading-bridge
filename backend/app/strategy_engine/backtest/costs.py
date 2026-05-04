"""Trading-cost model — fixed + percent + slippage + spread placeholder.

Each leg of a trade (entry and exit) pays:

    fixed_cost                ₹ flat per leg
    + percent_cost / 100 x notional  (percent of trade value)

Plus a *price* adjustment via ``adjust_for_slippage`` so that the
effective fill is **worse** than the bar's reference price:

    BUY  entry  → price + slippage% (pay more)
    BUY  exit   → price - slippage% (receive less)
    SELL entry  → price - slippage% (receive less)
    SELL exit   → price + slippage% (pay more)

``spread_percent`` is reserved for a future "half-spread" cost model
that separates bid-ask from slippage; in Phase 3 it is documented but
not applied — the simulator emits a warning if a non-zero spread is
configured so the operator knows it's a no-op until Phase 8 / 9.

All public functions are pure: input/output only, no module state.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.schema.strategy import Side


class CostSettings(BaseModel):
    """Per-leg cost configuration. Defaults to a frictionless backtest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fixed_cost: float = Field(default=0.0, ge=0)
    percent_cost: float = Field(default=0.0, ge=0)
    slippage_percent: float = Field(default=0.0, ge=0)
    spread_percent: float = Field(default=0.0, ge=0)


def leg_cost(*, price: float, quantity: float, settings: CostSettings) -> float:
    """₹ cost for one leg of a trade (entry OR exit).

    Returns a non-negative number; the caller subtracts it from P&L.
    """
    if price < 0 or quantity < 0:
        raise ValueError(
            f"price and quantity must be non-negative; got price={price}, quantity={quantity}."
        )
    notional = price * quantity
    return settings.fixed_cost + (settings.percent_cost / 100.0) * notional


def adjust_for_slippage(
    *,
    price: float,
    side: Side,
    leg: str,
    settings: CostSettings,
) -> float:
    """Return the slipped fill price.

    Args:
        price: Reference price (next-bar open for entry; trigger level
            or close for exit).
        side: Position side.
        leg: ``"entry"`` or ``"exit"``.
        settings: Cost settings; if ``slippage_percent == 0`` the price
            is returned unchanged.
    """
    if leg not in ("entry", "exit"):
        raise ValueError(f"leg must be 'entry' or 'exit'; got {leg!r}.")
    if settings.slippage_percent == 0:
        return price
    slip = settings.slippage_percent / 100.0
    # Worst-fill direction:
    #   BUY  entry adverse = +slip  (pay more)
    #   BUY  exit  adverse = -slip  (receive less)
    #   SELL entry adverse = -slip  (receive less)
    #   SELL exit  adverse = +slip  (pay more)
    if side is Side.BUY:
        sign = 1.0 if leg == "entry" else -1.0
    else:
        sign = -1.0 if leg == "entry" else 1.0
    return price * (1.0 + sign * slip)


__all__ = ["CostSettings", "adjust_for_slippage", "leg_cost"]
