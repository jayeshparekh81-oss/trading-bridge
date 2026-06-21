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

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.db.models.user import User

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
) -> User:
    """Premium-endpoint gate. Pass-through when ``PAYWALL_ENFORCED`` is off.

    Composes on :func:`get_current_active_user`, so 401 (unauthenticated) and
    403 (inactive account) fire first, unchanged.
    """
    if not get_settings().paywall_enforced:
        return user
    if not plan_is_active(user):
        _raise_plan_required()
    return user


__all__ = [
    "PAYWALL_STATUS_CODE",
    "PLAN_REQUIRED_CODE",
    "UPGRADE_URL",
    "plan_is_active",
    "require_active_plan",
]
