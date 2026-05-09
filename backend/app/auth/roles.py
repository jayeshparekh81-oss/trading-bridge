"""Role-based access helpers — Phase 1 of the locked RBAC sequence.

Today's surface:

    * :func:`is_admin(user)` — predicate over ``user.role``.
    * :func:`require_admin` — FastAPI dependency that raises ``403``
      with a Hinglish message when the caller isn't an admin.
    * :func:`require_role(role)` — factory for Phase 2's tier checks
      (``pro_user`` / ``creator`` / ``super_admin``). Phase 1 only
      uses it for ``"admin"``; the surface is intentionally
      forward-compatible so Phase 2 needs no API change.

Design notes:

    * The existing :class:`api.deps.get_current_admin` dependency
      reads ``user.is_admin`` directly. It is **not** modified by
      this module — production paths in
      :file:`backend/app/api/admin.py` keep working unchanged. New
      admin-only endpoints should use :func:`require_admin` from
      this module instead so they ride the ``role`` column the
      moment Phase 2 lands.

    * Hinglish copy on the 403 response — same voice as the rest of
      the user-facing surface. The message is short on purpose so
      the front-end can render it verbatim in a toast.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_active_user
from app.db.models.user import User

#: Locked Phase 1 vocabulary. Phase 2 extends this set without a
#: schema migration; tests pin the current set so a stray addition
#: trips a regression.
ROLE_USER = "user"
ROLE_ADMIN = "admin"

PHASE1_ROLES: frozenset[str] = frozenset({ROLE_USER, ROLE_ADMIN})


def is_admin(user: User) -> bool:
    """Predicate over ``user.role`` — does **not** read ``is_admin``.

    The two columns are kept in sync at-rest by Migration 013's
    backfill; a fresh row gets ``role='user'`` via the server default.
    Phase 2 collapses ``is_admin`` into a property derived from this
    function, but for now both columns coexist and this helper is the
    canonical reader for new code.
    """
    return user.role == ROLE_ADMIN


async def require_admin(
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """FastAPI dependency — pass through admin users, raise 403 otherwise.

    Composes on top of the existing
    :func:`app.api.deps.get_current_active_user` so authentication +
    activation are validated first (raising 401 / 403 on those gates)
    before the role check runs. The role-failure response is HTTP 403
    with a Hinglish detail so the frontend can render the message
    directly without translation.
    """
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yeh feature sirf admin ke liye hai.",
        )
    return user


def require_role(
    role: str,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Build a FastAPI dependency that requires a specific role.

    Phase 1 uses this only with ``"admin"`` (where it behaves
    identically to :func:`require_admin`). Phase 2 will use it with
    ``pro_user`` / ``creator`` / ``super_admin`` to gate paywalls,
    marketplace publishing, and infra-tier admin tools. The factory
    shape lets Phase 2 reuse the same dependency-injection idiom
    without each new role needing its own ``require_*`` function.
    """

    async def _dependency(
        user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Yeh feature sirf {role} ke liye hai.",
            )
        return user

    _dependency.__name__ = f"require_role_{role}"
    return _dependency


__all__ = [
    "PHASE1_ROLES",
    "ROLE_ADMIN",
    "ROLE_USER",
    "is_admin",
    "require_admin",
    "require_role",
]
