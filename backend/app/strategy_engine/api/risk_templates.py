"""Risk Templates CRUD — standalone Risk Builder backend.

Mirrors :mod:`entry_templates` / :mod:`exit_templates` for the
risk-management half of the strategy DSL. Endpoints (all
auth-scoped to the calling user; cross-user access returns 404 to
avoid id-enumeration probes):

    POST   /api/templates/risk            create
    GET    /api/templates/risk            list (newest first)
    GET    /api/templates/risk/{id}       fetch one
    PUT    /api/templates/risk/{id}       replace
    DELETE /api/templates/risk/{id}       hard-delete

The body shape carries the canonical ``RiskRules`` block under
``risk_rules`` plus ``name`` / ``description`` template metadata.
Validation runs through :class:`RiskRules.model_validate` so any
malformed value (negative cap, ``maxCapitalPerTradePercent`` >100,
non-int integer fields) fails the request before any DB write.

Note: ``RiskRules`` makes every field optional (defaults are 'no
cap'), so an empty ``risk_rules: {}`` is a *valid* template — it
just applies no caps. We don't reject empty here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.risk_template import RiskTemplate
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.schema.strategy import RiskRules

logger = get_logger("app.strategy_engine.api.risk_templates")

router = APIRouter(prefix="/api/templates/risk", tags=["risk-templates"])


# ─── Boundary models ───────────────────────────────────────────────────


class RiskTemplateCreate(BaseModel):
    """POST / PUT body. ``risk_rules`` is the canonical ``RiskRules``
    shape — validated against that model before persistence."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2_000)
    risk_rules: dict[str, Any] = Field(...)


class RiskTemplateRead(BaseModel):
    """Wire shape of a stored template — what the frontend renders."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    risk_rules: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RiskTemplateListResponse(BaseModel):
    templates: list[RiskTemplateRead]
    count: int


# ─── Helpers ───────────────────────────────────────────────────────────


def _validate_risk_shape(body: RiskTemplateCreate) -> None:
    """Run the canonical ``RiskRules`` validator over ``body.risk_rules``.

    Field-level violations (negative cap, ``maxCapitalPerTradePercent``
    >100, non-int integer fields) raise ``ValidationError`` here and
    surface as 422 with the first error message.
    """
    try:
        RiskRules.model_validate(body.risk_rules)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid risk block: {first.get('msg', 'validation error')}",
        ) from exc


async def _load_owned_template(
    db: AsyncSession, user: User, template_id: uuid.UUID
) -> RiskTemplate:
    """Fetch + ownership-scope check. 404 covers both 'not found'
    and 'not yours' so the endpoint isn't an enumeration oracle."""
    stmt = select(RiskTemplate).where(
        RiskTemplate.id == template_id,
        RiskTemplate.user_id == user.id,
    )
    template = (await db.execute(stmt)).scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found.",
        )
    return template


# ─── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=RiskTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_risk_template(
    body: RiskTemplateCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RiskTemplateRead:
    """Persist a new risk-management template for the calling user."""
    _validate_risk_shape(body)

    template = RiskTemplate(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        risk_rules=dict(body.risk_rules),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    logger.info(
        "risk_template.created",
        user_id=str(current_user.id),
        template_id=str(template.id),
        name=body.name,
    )
    return RiskTemplateRead.model_validate(template)


@router.get("", response_model=RiskTemplateListResponse)
async def list_risk_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RiskTemplateListResponse:
    """Every risk template owned by the calling user, newest first."""
    stmt = (
        select(RiskTemplate)
        .where(RiskTemplate.user_id == current_user.id)
        .order_by(RiskTemplate.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [RiskTemplateRead.model_validate(r) for r in rows]
    return RiskTemplateListResponse(templates=items, count=len(items))


@router.get("/{template_id}", response_model=RiskTemplateRead)
async def get_risk_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RiskTemplateRead:
    template = await _load_owned_template(db, current_user, template_id)
    return RiskTemplateRead.model_validate(template)


@router.put("/{template_id}", response_model=RiskTemplateRead)
async def update_risk_template(
    template_id: uuid.UUID,
    body: RiskTemplateCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RiskTemplateRead:
    """Replace the template — full PUT semantics, not partial PATCH."""
    _validate_risk_shape(body)
    template = await _load_owned_template(db, current_user, template_id)
    template.name = body.name
    template.description = body.description
    template.risk_rules = dict(body.risk_rules)
    await db.commit()
    await db.refresh(template)
    logger.info(
        "risk_template.updated",
        user_id=str(current_user.id),
        template_id=str(template.id),
    )
    return RiskTemplateRead.model_validate(template)


@router.delete(
    "/{template_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_risk_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    template = await _load_owned_template(db, current_user, template_id)
    await db.delete(template)
    await db.commit()
    logger.info(
        "risk_template.deleted",
        user_id=str(current_user.id),
        template_id=str(template_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
