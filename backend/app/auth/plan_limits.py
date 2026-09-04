"""Per-tier strategy quota — the ONE place ``feature_limits['strategies']`` is read
for enforcement.

Live values (migration 043): starter ``1``, pro ``3``, premium ``"all"`` — a
STRING sentinel, not a number. Anything that is not a positive int is treated
as unlimited, so a hand-edited or future value can never lock a paying
customer out of their own account (fail OPEN for the highest tier).

Count semantics: every ``strategies`` row the user owns, active or not, paper
or not. There is no soft-delete column; ``DELETE /api/strategies/{id}`` hard-
deletes, so a user can always free a slot by deleting. (The legacy
``DELETE /api/users/me/strategies/{id}`` only flips ``is_active`` and does NOT
free a slot — documented gap, founder's call.)

INERT while ``paywall_enforced`` is False: returns before touching the DB, so
the three creation paths are byte-for-byte today's behaviour for everyone.
During a user's grace window: no cap (full access, as promised).
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.entitlements import (
    PAYWALL_STATUS_CODE,
    PLAN_REQUIRED_CODE,
    UPGRADE_URL,
    plan_is_active,
    start_grace_if_needed,
    within_grace,
)
from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.subscription_plan import SubscriptionPlan
from app.db.models.user import User

#: A ``plan_status='none'`` user outside grace gets this many strategies.
FREE_STRATEGY_LIMIT = 1


def cap_from_feature_limits(blob: object) -> int | None:
    """Positive int cap, or ``None`` for unlimited (``"all"``, missing, odd)."""
    if isinstance(blob, dict):
        raw = blob.get("strategies")
        if isinstance(raw, bool):
            return None
        if isinstance(raw, int) and raw > 0:
            return raw
    return None


async def strategy_cap_for(db: AsyncSession, user: User) -> int | None:
    """The caller's cap: their active plan's ``strategies`` (None = unlimited),
    or :data:`FREE_STRATEGY_LIMIT` for a free user outside grace."""
    if plan_is_active(user):
        # A paying customer is never capped at the free limit: an active
        # plan_status with no linked plan row (plan_id SET NULL, deleted
        # plan, NULL feature_limits) is unlimited — fail OPEN.
        if user.active_plan_id is None:
            return None
        plan = await db.get(SubscriptionPlan, user.active_plan_id)
        return cap_from_feature_limits(plan.feature_limits if plan is not None else None)
    if within_grace(user):
        return None
    return FREE_STRATEGY_LIMIT


async def enforce_strategy_quota(db: AsyncSession, user: User) -> None:
    """Raise 402 ``PLAN_REQUIRED`` when the caller is at their tier's cap.

    No-op while ``paywall_enforced`` is False (no query). Starts the grace
    clock on first contact, like the premium gate does.
    """
    if not get_settings().paywall_enforced:
        return
    if user.paywall_grace_until is None and not plan_is_active(user):
        await start_grace_if_needed(db, user)
    cap = await strategy_cap_for(db, user)
    if cap is None:
        return
    used = int(
        (
            await db.execute(select(func.count(Strategy.id)).where(Strategy.user_id == user.id))
        ).scalar_one()
    )
    if used < cap:
        return
    raise HTTPException(
        status_code=PAYWALL_STATUS_CODE,
        detail={
            "code": PLAN_REQUIRED_CODE,
            "message": (
                f"Aapke plan mein {cap} strateg{'y' if cap == 1 else 'ies'} ki limit hai "
                f"({used} banayi hui). Upgrade karein, ya ek strategy delete karke jagah banayein."
            ),
            "upgrade_url": UPGRADE_URL,
            "limit": cap,
            "used": used,
        },
    )


__all__ = [
    "FREE_STRATEGY_LIMIT",
    "cap_from_feature_limits",
    "enforce_strategy_quota",
    "strategy_cap_for",
]
