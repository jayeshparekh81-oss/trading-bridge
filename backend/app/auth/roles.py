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
from typing import Annotated, Any, Literal

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_active_user
from app.db.models.user import User

#: Phase 1 vocabulary kept as-is. Phase 2 extends with three more
#: literals (``pro_user`` / ``creator`` / ``super_admin``); Migration
#: 014's CHECK constraint pins the locked five-tier set at the DB
#: level. Tests pin the current sets so any addition trips a
#: regression rather than landing silently.
ROLE_USER = "user"
ROLE_ADMIN = "admin"

PHASE1_ROLES: frozenset[str] = frozenset({ROLE_USER, ROLE_ADMIN})

# ─── Phase 2 RBAC vocabulary + hierarchy ─────────────────────────────

ROLE_PRO_USER = "pro_user"
ROLE_CREATOR = "creator"
ROLE_SUPER_ADMIN = "super_admin"

#: Locked five-tier role vocabulary. Order is the canonical
#: hierarchy on the user-track, with the admin-track tacked on the
#: end. Tests iterate this tuple.
USER_ROLES: tuple[str, ...] = (
    ROLE_USER,
    ROLE_PRO_USER,
    ROLE_CREATOR,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
)

PHASE2_ROLES: frozenset[str] = frozenset(USER_ROLES)

#: Pydantic-friendly ``Literal`` union of the locked vocabulary —
#: response models that surface the user's role can use it as a
#: typed field.
UserRole = Literal[
    "user", "pro_user", "creator", "admin", "super_admin"
]


# ─── Hierarchy: which roles include which permission set ─────────────
#
# Two parallel tracks per the locked design:
#
#     write track:   user ⊂ pro_user ⊂ creator
#     admin track:   admin ⊂ super_admin
#
# ``super_admin`` is "everything" — it covers both tracks (admin
# permissions AND every write tier). ``admin`` covers the write track
# implicitly because admin tooling reads + edits all user content.

#: Roles that satisfy the ``pro_user`` permission set — the paid tier
#: includes pro itself plus everyone above it on either track.
_PRO_OR_ABOVE: frozenset[str] = frozenset(
    {ROLE_PRO_USER, ROLE_CREATOR, ROLE_ADMIN, ROLE_SUPER_ADMIN}
)
_CREATOR_OR_ABOVE: frozenset[str] = frozenset(
    {ROLE_CREATOR, ROLE_ADMIN, ROLE_SUPER_ADMIN}
)
_ADMIN_OR_ABOVE: frozenset[str] = frozenset(
    {ROLE_ADMIN, ROLE_SUPER_ADMIN}
)


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


# ─── Phase 2 hierarchy predicates ────────────────────────────────────


def is_pro_or_above(user: User) -> bool:
    """True for ``pro_user`` and every higher-tier role."""
    return user.role in _PRO_OR_ABOVE


def is_creator_or_above(user: User) -> bool:
    """True for ``creator`` plus the admin track (``admin`` /
    ``super_admin``)."""
    return user.role in _CREATOR_OR_ABOVE


def is_admin_or_above(user: User) -> bool:
    """True for the admin track. Equivalent to ``is_admin(user) or
    is_super_admin(user)`` — kept as a separate helper so call sites
    that semantically mean "admin tooling" read clearly."""
    return user.role in _ADMIN_OR_ABOVE


def is_super_admin(user: User) -> bool:
    """True only for ``super_admin``."""
    return user.role == ROLE_SUPER_ADMIN


# ─── Phase 2 dependency factories ────────────────────────────────────


def _build_tier_dependency(
    label: str,
    allowed: frozenset[str],
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Build a FastAPI dependency that lets the user through when
    their role is in ``allowed`` and raises a 403 with a Hinglish
    message naming the tier otherwise.

    Shared by every ``require_*_or_above`` factory below so the
    error shape is identical across tiers — frontend renders the
    same toast structure for every block.
    """

    async def _dependency(
        user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Yeh feature sirf {label} ke liye hai.",
            )
        return user

    _dependency.__name__ = f"require_{label}"
    return _dependency


require_pro_user_or_above = _build_tier_dependency(
    "pro_user_or_above", _PRO_OR_ABOVE
)
require_creator_or_above = _build_tier_dependency(
    "creator_or_above", _CREATOR_OR_ABOVE
)
require_super_admin = _build_tier_dependency(
    "super_admin", frozenset({ROLE_SUPER_ADMIN})
)


__all__ = [
    "PHASE1_ROLES",
    "PHASE2_ROLES",
    "ROLE_ADMIN",
    "ROLE_CREATOR",
    "ROLE_PRO_USER",
    "ROLE_SUPER_ADMIN",
    "ROLE_USER",
    "USER_ROLES",
    "UserRole",
    "is_admin",
    "is_admin_or_above",
    "is_creator_or_above",
    "is_pro_or_above",
    "is_super_admin",
    "require_admin",
    "require_creator_or_above",
    "require_pro_user_or_above",
    "require_role",
    "require_super_admin",
]
