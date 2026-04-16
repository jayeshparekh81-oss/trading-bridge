"""P&L tracking service — feeds the kill switch.

Two scopes here:

* **Realized P&L** — updated immediately when a fill is reported. Stored
  in Redis under ``pnl:{user_id}`` and incremented atomically via the
  Redis client helpers.
* **Unrealized P&L** — summed from the cached position snapshot (stored
  under ``pos:{user_id}``). Stale by up to the cache TTL (default 5 min)
  which is fine for the kill switch: a user with a sudden adverse move
  will almost certainly have a new trade or quote refresh landing before
  the stale window matters.

The kill switch reads :func:`calculate_daily_pnl` every time a new
webhook arrives; any change here ripples straight into that gate, so
correctness (Decimals, not floats) beats performance micro-optimisations.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core import redis_client
from app.core.logging import get_logger
from app.schemas.broker import Position

if TYPE_CHECKING:
    import redis.asyncio as aioredis


logger = get_logger("app.services.pnl_service")


# ═══════════════════════════════════════════════════════════════════════
# Realized P&L
# ═══════════════════════════════════════════════════════════════════════


async def record_realized_pnl(
    user_id: UUID | str,
    delta: Decimal,
    *,
    redis_conn: aioredis.Redis | None = None,
) -> Decimal:
    """Add a realized fill's P&L to the daily running total.

    Returns the new running total — useful for the kill switch to evaluate
    the breach inline without a second round-trip.
    """
    if not isinstance(delta, Decimal):
        raise TypeError("record_realized_pnl expects Decimal")
    return await redis_client.increment_daily_pnl(
        user_id, delta, redis_client=redis_conn
    )


async def get_realized_pnl(
    user_id: UUID | str, *, redis_conn: aioredis.Redis | None = None
) -> Decimal:
    """Read the cached realized-P&L total (zero if none recorded today)."""
    return await redis_client.get_daily_pnl(user_id, redis_client=redis_conn)


# ═══════════════════════════════════════════════════════════════════════
# Position cache + unrealized P&L
# ═══════════════════════════════════════════════════════════════════════


async def update_position_cache(
    user_id: UUID | str,
    positions: list[Position],
    *,
    redis_conn: aioredis.Redis | None = None,
) -> None:
    """Snapshot the broker's current positions into Redis.

    Input is the broker-native :class:`Position` list; we serialise a
    minimal dict (symbol, exchange, quantity, avg_price, ltp,
    unrealized_pnl, product_type) so reads don't require the Pydantic
    validator to run on every kill-switch evaluation.
    """
    payload = [_position_to_dict(p) for p in positions]
    await redis_client.set_positions_cache(
        user_id, payload, redis_client=redis_conn
    )


async def get_positions_from_cache(
    user_id: UUID | str, *, redis_conn: aioredis.Redis | None = None
) -> list[dict[str, Any]]:
    """Read the cached snapshot (empty list on miss)."""
    return await redis_client.get_positions_cache(
        user_id, redis_client=redis_conn
    )


async def calculate_unrealized_pnl(
    user_id: UUID | str, *, redis_conn: aioredis.Redis | None = None
) -> Decimal:
    """Sum ``unrealized_pnl`` across the cached positions snapshot.

    Missing cache → ``Decimal("0")``. Corrupt individual entries are
    skipped with a warning rather than blowing up the kill switch — a
    single bad JSON field must not mask a real breach.
    """
    cached = await get_positions_from_cache(user_id, redis_conn=redis_conn)
    total = Decimal("0")
    for entry in cached:
        raw = entry.get("unrealized_pnl")
        if raw is None:
            continue
        try:
            total += Decimal(str(raw))
        except (ValueError, ArithmeticError):
            logger.warning(
                "pnl.bad_unrealized_entry", user_id=str(user_id), entry=entry
            )
    return total


async def calculate_daily_pnl(
    user_id: UUID | str, *, redis_conn: aioredis.Redis | None = None
) -> Decimal:
    """Realized + unrealized for the current trading day."""
    realized = await get_realized_pnl(user_id, redis_conn=redis_conn)
    unrealized = await calculate_unrealized_pnl(user_id, redis_conn=redis_conn)
    return realized + unrealized


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _position_to_dict(position: Position) -> dict[str, Any]:
    """Serialise a Position with Decimal values rendered as strings.

    JSON in Redis is ``str``-only; keeping Decimals as strings avoids the
    floating-point round-trip that would silently corrupt rupee values.
    """
    return {
        "symbol": position.symbol,
        "exchange": position.exchange.value,
        "quantity": position.quantity,
        "avg_price": str(position.avg_price),
        "ltp": str(position.ltp),
        "unrealized_pnl": str(position.unrealized_pnl),
        "product_type": position.product_type.value,
    }


__all__ = [
    "calculate_daily_pnl",
    "calculate_unrealized_pnl",
    "get_positions_from_cache",
    "get_realized_pnl",
    "record_realized_pnl",
    "update_position_cache",
]
