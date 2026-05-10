"""License compliance dashboard API.

Pure read endpoints over the indicator registry + strategies
table — never writes anything, never mutates registry state.

User endpoints (any authenticated user, scoped to ``current_user.id``):

    GET /api/compliance/strategies/me   list summaries for caller's strategies
    GET /api/compliance/strategies/{id} full report for one owned strategy

Admin endpoints (``require_admin``):

    GET /api/compliance/indicators       per-indicator usage roll-up
    GET /api/compliance/strategies/all   paginated cross-user reports

Cross-user enumeration is handled by returning 404 (not 403) when a
non-admin requests a strategy they don't own — same pattern the
strategies CRUD router uses, so a probing user can't differentiate
"exists but not yours" from "doesn't exist".
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.auth.roles import require_admin
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.compliance import (
    LicenseUsageStats,
    StrategyComplianceReport,
    StrategyComplianceSummary,
    compute_indicator_usage_stats,
    evaluate_strategy_compliance,
    summarise_strategy,
)

logger = get_logger("app.strategy_engine.api.compliance")

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


# ─── Wire shapes ──────────────────────────────────────────────────────


class StrategyComplianceList(BaseModel):
    """List response wrapper for the user's per-strategy summaries."""

    model_config = ConfigDict(from_attributes=False)

    strategies: list[StrategyComplianceSummary]
    count: int


class IndicatorUsageList(BaseModel):
    """Admin: per-indicator usage roll-up wrapper."""

    model_config = ConfigDict(from_attributes=False)

    indicators: list[LicenseUsageStats]
    count: int


class AdminStrategyComplianceList(BaseModel):
    """Admin: paginated per-strategy reports across all users."""

    model_config = ConfigDict(from_attributes=False)

    strategies: list[StrategyComplianceReport]
    count: int = Field(
        ..., description="Number of items returned in this page."
    )
    has_more: bool = Field(
        ...,
        description=(
            "True iff additional rows exist past the current "
            "``offset + limit`` window."
        ),
    )


# ─── User endpoints ───────────────────────────────────────────────────


@router.get("/strategies/me", response_model=StrategyComplianceList)
async def my_compliance_summary(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyComplianceList:
    """Compact per-strategy compliance summary for every strategy
    the calling user owns. Sized for the dashboard list view —
    full per-indicator detail comes from the per-strategy endpoint.
    """
    rows = (
        (
            await db.execute(
                select(Strategy)
                .where(Strategy.user_id == current_user.id)
                .order_by(Strategy.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    summaries = [
        summarise_strategy(
            evaluate_strategy_compliance(
                strategy_id=row.id,
                strategy_name=row.name,
                strategy_json=row.strategy_json or {},
            )
        )
        for row in rows
    ]
    return StrategyComplianceList(strategies=summaries, count=len(summaries))


# ─── Admin endpoints ──────────────────────────────────────────────────
#
# Defined BEFORE ``/strategies/{strategy_id}`` so the literal
# ``/strategies/all`` route wins the FastAPI registration-order
# match. Otherwise the parameterised path catches "all" first and
# tries to parse it as a UUID → 422 instead of running the admin
# handler.


@router.get("/indicators", response_model=IndicatorUsageList)
async def indicator_usage_stats(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> IndicatorUsageList:
    """Per-indicator usage roll-up across every strategy on the
    platform. One row per known registry id (zero-usage entries
    included for completeness) plus synthetic rows for any unknown
    ids strategies reference.
    """
    rows = (await db.execute(select(Strategy))).scalars().all()
    stats = compute_indicator_usage_stats(rows)
    return IndicatorUsageList(indicators=stats, count=len(stats))


@router.get(
    "/strategies/all", response_model=AdminStrategyComplianceList
)
async def admin_all_strategies(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_score: int | None = Query(
        default=None,
        ge=0,
        le=100,
        description=(
            "Filter to strategies whose compliance score is at most "
            "this value — useful for finding the worst offenders. "
            "Applied after evaluation, so the response ``count`` is "
            "the post-filter count of the page."
        ),
    ),
) -> AdminStrategyComplianceList:
    """Cross-user compliance reports.

    Pagination is offset/limit because we've kept the on-disk
    ordering stable (``created_at DESC``) and the admin page
    doesn't need cursor stability under concurrent writes —
    admins are reading, not paging through a hot stream.
    """
    base = select(Strategy).order_by(Strategy.created_at.desc())
    rows = (
        (await db.execute(base.offset(offset).limit(limit + 1)))
        .scalars()
        .all()
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    reports = [
        evaluate_strategy_compliance(
            strategy_id=row.id,
            strategy_name=row.name,
            strategy_json=row.strategy_json or {},
        )
        for row in page
    ]
    if min_score is not None:
        reports = [r for r in reports if r.compliance_score <= min_score]
    return AdminStrategyComplianceList(
        strategies=reports,
        count=len(reports),
        has_more=has_more,
    )


# ─── User per-strategy detail (parameterised — registered LAST) ──────


@router.get(
    "/strategies/{strategy_id}", response_model=StrategyComplianceReport
)
async def strategy_compliance_detail(
    strategy_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyComplianceReport:
    """Full per-indicator compliance report for one owned strategy.

    Cross-user requests get 404 — same convention as the strategies
    CRUD router.
    """
    row = (
        await db.execute(
            select(Strategy).where(
                Strategy.id == strategy_id,
                Strategy.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found.",
        )
    return evaluate_strategy_compliance(
        strategy_id=row.id,
        strategy_name=row.name,
        strategy_json=row.strategy_json or {},
    )


__all__ = ["router"]
