"""Billing entitlement gate — Phase 2 Billing B3.

:func:`require_active_plan` is the premium-feature FastAPI dependency. It reads
**only** the B2 billing columns ``plan_status`` + ``plan_expires_at`` — never
``role`` or ``live_trading_enabled``. Billing is orthogonal to RBAC by design;
the role track lives in :mod:`app.auth.roles` and is untouched here.

Fail-open by design:

    * ``PAYWALL_ENFORCED`` OFF (default) ⇒ pure pass-through, identical to
      :func:`app.api.deps.get_current_active_user`. Attaching this dependency
      to an endpoint is therefore behavior-neutral until the flag is flipped.
    * ``none`` / ``expired`` / ``cancelled`` / any unknown status, or an
      ``active`` plan whose ``plan_expires_at`` has lapsed ⇒ treated as
      free-tier: premium is denied but ALL free access is retained, because
      free endpoints never depend on this gate.

B3.0 ships this **inert** — it is wired to no endpoint. B3.2 attaches it to the
premium endpoints (analytics / trade history / ledger).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, NoReturn

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.db.models.user import User
from app.db.session import get_session

#: Stable machine code the frontend branches on to render the upgrade wall.
#: This is the real contract — independent of the HTTP status code below.
PLAN_REQUIRED_CODE = "PLAN_REQUIRED"

#: Where the frontend should send the user to subscribe.
UPGRADE_URL = "/pricing"

#: HTTP status for a paywall block. ``402 Payment Required`` is the exact
#: semantic and is distinct from 401 (unauthenticated) and 403 (RBAC-forbidden),
#: so the frontend can branch on the status alone. If any edge/CDN mishandles
#: 402, switching this single constant to ``status.HTTP_403_FORBIDDEN`` flips
#: the whole gate to 403 — the ``PLAN_REQUIRED_CODE`` body remains the contract.
PAYWALL_STATUS_CODE = status.HTTP_402_PAYMENT_REQUIRED


def plan_is_active(user: User) -> bool:
    """True only for a genuinely active, non-expired plan. **NON-RAISING.**

    The shared entitlement predicate: used by :func:`require_active_plan`
    (the 402-gate) AND by response-field gating (B3.3 backtest) that must
    branch without raising — backtest is free-with-premium-fields, never
    402-gated.

    Reads ``plan_status`` + ``plan_expires_at`` ONLY. Everything else —
    ``none`` / ``expired`` / ``cancelled`` / any unknown status, or an
    ``active`` row whose expiry has lapsed — is free-tier (returns False).
    """
    if user.plan_status != "active":
        return False
    expires = user.plan_expires_at
    if expires is None:
        return True  # active with no expiry = perpetual entitlement
    # Defensive: prod stores TIMESTAMPTZ (tz-aware); coerce a naive value to
    # UTC so a stray naive datetime can never raise here (would 500 the gate).
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires > datetime.now(UTC)


def within_grace(user: User) -> bool:
    """True while a started, unexpired grace window is running. NON-RAISING.

    Reads ``paywall_grace_until`` only. NULL = grace never started = False.
    """
    until = user.paywall_grace_until
    if until is None:
        return False
    if until.tzinfo is None:  # defensive, mirrors plan_is_active
        until = until.replace(tzinfo=UTC)
    return until > datetime.now(UTC)


def has_premium_access(user: User) -> bool:
    """The ONE predicate every premium gate branches on. NON-RAISING.

    Flag off ⇒ True for everyone (identical to today). Flag on ⇒ an active
    plan, or a running grace window. Use this instead of re-deriving the rule
    inline (backtest's premium-field gating does), so grace cannot be
    honoured by one gate and ignored by another.
    """
    if not get_settings().paywall_enforced:
        return True
    return plan_is_active(user) or within_grace(user)


async def start_grace_if_needed(db: AsyncSession, user: User) -> bool:
    """One-shot: stamp ``now + paywall_grace_days`` on a free user the first
    time entitlement is checked after the flag is flipped. Idempotent — a
    non-NULL value is never extended or reset, so it cannot be milked.

    No-op (returns False) while the flag is off, when grace is 0 days, when
    the user already has an active plan, or when the clock already started.
    Commits its own one-column write.
    """
    settings = get_settings()
    if not settings.paywall_enforced or int(settings.paywall_grace_days) <= 0:
        return False
    if user.paywall_grace_until is not None or plan_is_active(user):
        return False
    user.paywall_grace_until = datetime.now(UTC) + timedelta(days=int(settings.paywall_grace_days))
    await db.commit()
    return True


def _raise_plan_required() -> NoReturn:
    """Raise the machine-distinguishable paywall response."""
    raise HTTPException(
        status_code=PAYWALL_STATUS_CODE,
        detail={
            "code": PLAN_REQUIRED_CODE,
            "message": "Yeh premium feature hai — apna plan upgrade karein.",
            "upgrade_url": UPGRADE_URL,
        },
    )


async def require_active_plan(
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession | None, Depends(get_session)] = None,
) -> User:
    """Premium-endpoint gate. Pass-through when ``PAYWALL_ENFORCED`` is off.

    Composes on :func:`get_current_active_user`, so 401 (unauthenticated) and
    403 (inactive account) fire first, unchanged. With the flag on, a free
    user's first gated request STARTS their grace clock (one write, once) and
    passes; after the window a 402 ``PLAN_REQUIRED`` follows.
    """
    if not get_settings().paywall_enforced:
        return user
    if plan_is_active(user):
        return user
    if user.paywall_grace_until is None and db is not None:
        await start_grace_if_needed(db, user)
    if within_grace(user):
        return user
    _raise_plan_required()


__all__ = [
    "PAYWALL_STATUS_CODE",
    "PLAN_REQUIRED_CODE",
    "UPGRADE_URL",
    "has_premium_access",
    "plan_is_active",
    "require_active_plan",
    "start_grace_if_needed",
    "within_grace",
]
