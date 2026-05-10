"""Per-user feature gates that combine a global flag with a user column.

Phase 8B-1 discovery flagged ``LIVE_TRADING_ENABLED`` as
process-global; the launch plan requires manual per-user approval
before real-money orders are placed. Migration 011 added the
``users.live_trading_enabled`` boolean column, and this module
implements the **AND** combinator the live-orders SafetyChain calls:

    is_live_trading_enabled_for_user(db, user_id) ⇔
        feature_flags.is_enabled("LIVE_TRADING_ENABLED")
        AND  user.live_trading_enabled

Both must be true. The global flag remains the platform-level
kill-switch ("turn live trading off for everyone right now") and
per-user column carries the day-to-day approval state. The
combination is defence-in-depth: revoking the global flag instantly
blocks every user, while revoking one user's column only blocks them.

The function returns ``False`` when:

* The global flag is off (any source — env, runtime override, default).
* The per-user row exists but ``live_trading_enabled`` is ``False``.
* The user id does not exist (treated as "no permission" rather than
  raised — the SafetyChain logs the failure as one row in its
  per-check verdict; raising here would force the chain to special-
  case auth lookups).

Module placement note: this helper lives in ``live_orders`` rather
than ``feature_flags`` because the feature_flags package has a
load-bearing AST-purity test that forbids ``app.db`` and
``sqlalchemy`` imports — the manager must stay stdlib-only for
deterministic test isolation. The combinator legitimately needs both
the flag manager AND the User row, so it lives one level up at the
SafetyChain's natural home.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.strategy_engine.feature_flags import manager


async def is_live_trading_enabled_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> bool:
    """Return ``True`` only if the global flag AND the user column are on.

    The global flag is checked **first** — when it is off the user row
    is not loaded at all. That ordering matters: an emergency platform-
    wide disable must short-circuit before any DB I/O so it takes
    effect even if the database itself is misbehaving.
    """
    if not manager.is_enabled("LIVE_TRADING_ENABLED"):
        return False

    stmt = select(User.live_trading_enabled).where(User.id == user_id)
    result = (await db.execute(stmt)).scalar_one_or_none()
    if result is None:
        return False
    return bool(result)


__all__ = ["is_live_trading_enabled_for_user"]
