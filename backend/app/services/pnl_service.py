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

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.core.logging import get_logger
from app.schemas.broker import Position

if TYPE_CHECKING:
    import redis.asyncio as aioredis


logger = get_logger("app.services.pnl_service")

#: The trading day is an IST calendar day — the brake is a DAILY loss cap and
#: "today" must mean the founder's today, not UTC's.
_IST = timezone(timedelta(hours=5, minutes=30))


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
    return await redis_client.increment_daily_pnl(user_id, delta, redis_client=redis_conn)


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
    await redis_client.set_positions_cache(user_id, payload, redis_client=redis_conn)


async def get_positions_from_cache(
    user_id: UUID | str, *, redis_conn: aioredis.Redis | None = None
) -> list[dict[str, Any]]:
    """Read the cached snapshot (empty list on miss)."""
    return await redis_client.get_positions_cache(user_id, redis_client=redis_conn)


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
            logger.warning("pnl.bad_unrealized_entry", user_id=str(user_id), entry=entry)
    return total


async def realized_pnl_today_from_db(
    session: AsyncSession, user_id: UUID | str, *, now: datetime | None = None
) -> Decimal:
    """Realised P&L booked TODAY (IST), read from the database.

    🔴 WHY THIS EXISTS — THE DEAD SAFETY NUMBER (found 2026-09-10).

    Everything above this line reads Redis, and **nothing in production has
    ever written those keys**. ``record_realized_pnl`` and
    ``update_position_cache`` have zero production callers; the only writer of
    ``pnl:{user}`` is ``kill_switch_service.manual_reset``, which writes the
    literal ``0``. There are no ``pnl:*`` or ``pos:*`` keys on prod Redis at
    all.

    So ``calculate_daily_pnl`` returned exactly ``Decimal("0")`` every time it
    has ever been called. The founder's ₹2,00,000 ``max_daily_loss_inr`` brake
    evaluates ``daily_pnl < -max_daily_loss``, which ``0`` can never satisfy:
    **the loss brake has never been capable of tripping.** The dashboard's
    "Aaj ka P&L" printed a confident ₹0.00 from the same dead source.

    This reads the fact from where it actually lives — closed positions with a
    reconciled ``final_pnl`` — so the brake has a real number to judge.

    FAIL-SAFE BY CONSTRUCTION. It sums only P&L that is actually recorded, so
    it can never manufacture a loss and trip the brake spuriously. Its failure
    mode is the one we already have (under-reporting, so a brake that does not
    fire), never a false halt on a live account.

    KNOWN LAG, stated rather than hidden: ``final_pnl`` is written by the P&L
    reconciler on its own schedule, so a position closed minutes ago may not be
    counted yet. That is a smaller gap than "never", and closing it properly
    means writing realised P&L on the execution path — a change to the sacred
    files, which is not in scope here.
    """
    # Imported lazily: this module is imported by the kill switch, and the
    # kill switch must not acquire a model-layer import cycle for a helper
    # most callers never reach.
    from app.db.models.strategy import Strategy
    from app.db.models.strategy_position import StrategyPosition

    moment = now or datetime.now(_IST)
    start_ist = moment.astimezone(_IST).replace(hour=0, minute=0, second=0, microsecond=0)
    total = (
        await session.execute(
            select(func.coalesce(func.sum(StrategyPosition.final_pnl), 0))
            .select_from(StrategyPosition)
            .join(Strategy, Strategy.id == StrategyPosition.strategy_id)
            .where(
                StrategyPosition.user_id == user_id,
                StrategyPosition.status == "closed",
                StrategyPosition.final_pnl.is_not(None),
                StrategyPosition.closed_at.is_not(None),
                # BOUNDED AT BOTH ENDS. An open-ended ``>= start`` sums the
                # day and everything after it, so a row closed tomorrow — a
                # backdated correction, a clock-skewed write — would count
                # against TODAY's loss cap. It is a daily brake; it gets
                # exactly one day.
                StrategyPosition.closed_at >= start_ist.astimezone(UTC),
                StrategyPosition.closed_at < (start_ist + timedelta(days=1)).astimezone(UTC),
                # A paper strategy's P&L must never reach a live money brake.
                Strategy.is_paper.is_(False),
                # Owner rows only — a subscriber's simulated fill is not the
                # owner's loss (migration 034).
                StrategyPosition.subscription_id.is_(None),
            )
        )
    ).scalar_one()
    return Decimal(str(total))


async def calculate_daily_pnl(
    user_id: UUID | str,
    *,
    redis_conn: aioredis.Redis | None = None,
    session: AsyncSession | None = None,
) -> Decimal:
    """Realized + unrealized for the current trading day.

    When a ``session`` is supplied AND the Redis counter reads zero, the
    realised half falls back to the DATABASE (see
    :func:`realized_pnl_today_from_db`). Without a session, behaviour is
    byte-identical to before — so no caller that has not been updated can
    change behaviour by accident.

    ⚠️ The UNREALISED half is still read from a position cache that nothing
    populates, so it is still structurally ``0``. Mark-to-market on an open
    position therefore remains invisible to the brake. Fixing that needs a
    writer for ``pos:{user}`` fed by a live quote — stated here so the
    remaining half of the gap is not mistaken for closed.
    """
    realized = await get_realized_pnl(user_id, redis_conn=redis_conn)
    if session is not None and realized == 0:
        # Redis FIRST, database as the fallback — and the order matters.
        #
        # The counter is incremented per fill, so when it is live it is the
        # fresher number and must win. In production it is never written at
        # all, so it reads exactly ``0`` and this fallback is what actually
        # runs. Treating a ``0`` as "no data" is safe in both directions: a
        # genuine zero (nothing closed today) makes the DB sum zero too, so
        # the answer is unchanged, while a dead counter finally yields to a
        # source that has the fact.
        realized = await realized_pnl_today_from_db(session, user_id)
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
