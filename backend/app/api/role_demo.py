"""Role-tier demonstration endpoints — Phase 2 RBAC.

Four endpoints under ``/api/roles/*`` that exercise each new
dependency factory shipped in :mod:`app.auth.roles`. Phase 3 wires
real role-gated features (paywalled indicators, marketplace publish,
billing controls); these endpoints exist now so:

    * The dependency factories have a smoke-test surface that
      proves the wiring round-trips through the full FastAPI
      stack — not just the unit-tested hook.
    * Frontend can build its tier-aware UX (paywall walls, "creator
      badge" affordance, super-admin tools) against a stable
      contract before the real endpoints land.

Removable: when Phase 3 ships actual paywalled / publishing /
super-admin endpoints, these demo routes can be deleted in the
same commit (the helpers move along; no other code depends on
``role_demo`` itself).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.auth.roles import (
    require_creator_or_above,
    require_pro_user_or_above,
    require_super_admin,
)
from app.db.models.user import User

router = APIRouter(prefix="/api/roles", tags=["rbac"])


@router.get("/me")
async def get_my_role(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, Any]:
    """Return the current user's role + a summary of which tiers
    they have access to. Available to any authenticated user."""
    return {
        "user_id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "tiers": {
            "is_pro_or_above": current_user.is_pro_or_above,
            "is_creator_or_above": current_user.is_creator_or_above,
            "is_super_admin": current_user.is_super_admin,
        },
    }


@router.get("/pro/feature")
async def pro_feature_demo(
    current_user: Annotated[User, Depends(require_pro_user_or_above)],
) -> dict[str, str]:
    """Demo endpoint gated by ``require_pro_user_or_above``.

    Phase 3 replaces this with a real paywalled route — extra
    indicator slots, more concurrent strategies, priority support
    queue, etc. The contract the frontend ships against (200 with
    the user's tier echoed back) stays.
    """
    return {
        "feature": "pro_feature_demo",
        "tier_required": "pro_user_or_above",
        "your_role": current_user.role,
    }


@router.get("/creator/publish")
async def creator_publish_demo(
    current_user: Annotated[User, Depends(require_creator_or_above)],
) -> dict[str, str]:
    """Demo endpoint gated by ``require_creator_or_above``.

    Phase 3 replaces this with the marketplace-publish action.
    Same contract shape so frontend can prototype the publishing
    workflow today.
    """
    return {
        "feature": "creator_publish_demo",
        "tier_required": "creator_or_above",
        "your_role": current_user.role,
    }


@router.get("/super-admin/system")
async def super_admin_system_demo(
    current_user: Annotated[User, Depends(require_super_admin)],
) -> dict[str, str]:
    """Demo endpoint gated by ``require_super_admin``.

    Phase 3 replaces this with billing toggles + critical
    infrastructure controls (DB connection pools, kill-everything
    flags). Strict tier — admin alone is NOT sufficient.
    """
    return {
        "feature": "super_admin_system_demo",
        "tier_required": "super_admin",
        "your_role": current_user.role,
    }


__all__ = ["router"]
