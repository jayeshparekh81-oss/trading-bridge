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
from app.db.models.subscription_plan_price import TENOR_MONTHS, SubscriptionPlanPrice
from app.db.session import get_session

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class PlanPriceOut(BaseModel):
    """One sellable (tier, tenor) with its own Razorpay handle.

    ``price_per_month_inr`` is the PER-MONTH figure the cards show;
    ``total_billed_inr`` is what actually gets charged up front.
    ``discount_pct`` is derived from the tier's own monthly price, so the
    ladder can never drift from the numbers.
    """

    tenor: str
    price_per_month_inr: float
    months_billed: int
    total_billed_inr: float
    discount_pct: int
    razorpay_plan_id: str | None = None


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
    #: All sellable tenors, cheapest-per-month last. Empty only if 041 has not
    #: run yet — the surfaces fall back to the legacy scalars in that case.
    prices: list[PlanPriceOut] = []


class PlansResponse(BaseModel):
    plans: list[PlanOut]


def _prices_for(
    plan: SubscriptionPlan, rows: list[SubscriptionPlanPrice]
) -> list[PlanPriceOut]:
    """Build the tenor list, deriving the discount from the tier's OWN monthly
    price so the ladder can never disagree with the numbers shown."""
    base = next(
        (float(r.price_per_month_inr) for r in rows if r.tenor == "monthly"), None
    ) or float(plan.price_monthly_inr or 0)
    out: list[PlanPriceOut] = []
    for r in rows:
        per_month = float(r.price_per_month_inr)
        months = int(r.months_billed or TENOR_MONTHS.get(r.tenor, 1))
        pct = round((1 - per_month / base) * 100) if base else 0
        out.append(
            PlanPriceOut(
                tenor=r.tenor,
                price_per_month_inr=per_month,
                months_billed=months,
                total_billed_inr=round(per_month * months, 2),
                discount_pct=max(0, pct),
                razorpay_plan_id=r.razorpay_plan_id,
            )
        )
    return out


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

    # One query for every tenor across every plan (no N+1).
    price_rows = (
        (
            await db.execute(
                select(SubscriptionPlanPrice)
                .where(SubscriptionPlanPrice.is_active.is_(True))
                .order_by(SubscriptionPlanPrice.sort_order)
            )
        )
        .scalars()
        .all()
    )
    by_plan: dict[str, list[SubscriptionPlanPrice]] = {}
    for pr in price_rows:
        by_plan.setdefault(str(pr.plan_id), []).append(pr)
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
                prices=_prices_for(p, by_plan.get(str(p.id), [])),
            )
            for p in rows
        ]
    )
