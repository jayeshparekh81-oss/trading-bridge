"""Symbol-agnostic open-position lookup for exit-class webhook actions.

Exit signals (PARTIAL / EXIT / SL_HIT) must act on the position the strategy
ALREADY HOLDS — identified by its stored, entry-time trading symbol — never by a
freshly re-resolved contract symbol.

Why this exists (incident class, 2026-05-26)
--------------------------------------------
``strategy_webhook`` re-resolves the TradingView ticker to the month-stamped
contract via ``futures_resolver`` on *every* action. On an F&O **expiry day** in
the 14:30-15:30 IST window the resolver rolls to the **next** month. For an exit
that means the re-resolved symbol no longer matches the still-open current-month
position, the symbol-keyed lookup misses, and the exit **silently no-ops** —
leaving the position to auto-settle at the exchange close. Internal exits
(position_manager / kill_switch) were already safe because they use the stored
``position.symbol``; Pine-driven direct exits were not.

This helper finds the open position by ``strategy_id`` (+ optional side),
**independent of symbol**, so the webhook can pin the exit to the held contract.

See ``docs/DEPLOY_RUNBOOK_EXIT_FIX_20260526.md``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.strategy_position import StrategyPosition

#: StrategyPosition lifecycle is ``open | partial | closed`` (see the model
#: docstring); "still has exposure" == open or partial. Mirrors every other
#: open-position query in the codebase (direct_exit / position_manager /
#: kill_switch / strategy_executor all use this exact tuple).
_OPEN_STATUSES: tuple[str, ...] = ("open", "partial")


def _normalize_side(side: str | None) -> str | None:
    """Map a payload side to the stored ``OrderSide`` spelling, or ``None``.

    Pine/native payloads send ``long``/``short`` (or legacy ``buy``/``sell``);
    ``strategy_positions.side`` stores ``buy``/``sell``. Mirrors ``direct_exit``
    so lookups agree. An unrecognized side returns ``None`` → caller treats it as
    "no side filter" (defensive: a malformed side must not *hide* an open
    position — failing to find one is the very bug we are fixing).
    """
    if not side:
        return None
    s = side.strip().lower()
    if s in ("long", "buy"):
        return "buy"
    if s in ("short", "sell"):
        return "sell"
    return None


async def find_open_position_by_strategy(
    session: AsyncSession,
    *,
    strategy_id: UUID,
    side: str | None = None,
) -> StrategyPosition | None:
    """Most-recently-opened open/partial position for a strategy, symbol-agnostic.

    When *side* normalizes to buy/sell it is filtered; otherwise no side filter
    is applied. Returns the most recent match by ``opened_at``, or ``None`` when
    the strategy genuinely holds no open position.
    """
    stmt = select(StrategyPosition).where(
        StrategyPosition.strategy_id == strategy_id,
        StrategyPosition.status.in_(_OPEN_STATUSES),
        # OWNER scope only (migration 034): exit-pin must never resolve to a
        # marketplace subscriber's PAPER position. Owner rows are NULL → this
        # matches exactly today's rows (byte-identical).
        StrategyPosition.subscription_id.is_(None),
    )
    side_lc = _normalize_side(side)
    if side_lc is not None:
        stmt = stmt.where(StrategyPosition.side == side_lc)
    stmt = stmt.order_by(StrategyPosition.opened_at.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()
