"""Public pricing endpoint — ``GET /api/pricing/plans`` (Phase 2 Billing B1).

Serves the platform subscription tiers from the ``subscription_plans`` table
so the pricing surfaces read one DB source instead of hardcoded arrays.

PUBLIC: viewing pricing requires no auth, so there is deliberately no
``get_current_user`` / role dependency here — only a DB session. Read-only;
returns active plans ordered by ``sort_order``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.subscription_plan import SubscriptionPlan
from app.db.session import get_session

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class PlanOut(BaseModel):
    """A single subscription tier as the pricing pages consume it.

    Prices are emitted as plain numbers (Decimal → float) so the frontend
    renders ``₹999`` unchanged. ``feature_limits`` is passed through opaque.
    """

    id: str
    name: str
    tier: str
    price_monthly_inr: float
    price_yearly_inr: float
    feature_limits: dict[str, Any]
    sort_order: int


class PlansResponse(BaseModel):
    plans: list[PlanOut]


@router.get("/plans", response_model=PlansResponse)
async def list_plans(
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PlansResponse:
    """Return active subscription plans, ordered by ``sort_order``."""
    rows = (
        (
            await db.execute(
                select(SubscriptionPlan)
                .where(SubscriptionPlan.is_active.is_(True))
                .order_by(SubscriptionPlan.sort_order)
            )
        )
        .scalars()
        .all()
    )
    return PlansResponse(
        plans=[
            PlanOut(
                id=str(p.id),
                name=p.name,
                tier=p.tier,
                price_monthly_inr=float(p.price_monthly_inr),
                price_yearly_inr=float(p.price_yearly_inr),
                feature_limits=p.feature_limits or {},
                sort_order=p.sort_order,
            )
            for p in rows
        ]
    )
