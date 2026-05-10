"""Exit Templates CRUD — standalone Exit Builder backend.

Mirrors :mod:`entry_templates` for the exit half of the strategy
DSL. Endpoints (all auth-scoped to the calling user; cross-user
access returns 404 to avoid id-enumeration probes):

    POST   /api/templates/exit            create
    GET    /api/templates/exit            list (newest first)
    GET    /api/templates/exit/{id}       fetch one
    PUT    /api/templates/exit/{id}       replace
    DELETE /api/templates/exit/{id}       hard-delete

The body shape carries the canonical ``ExitRules`` block under
``exit_rules`` plus ``name`` / ``description`` / ``indicators_used``
template metadata. Validation runs through
:class:`ExitRules.model_validate` so any malformed sub-field — and
the ``_at_least_one_exit`` model_validator — fail the request
before any DB write.
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
from app.db.models.exit_template import ExitTemplate
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.schema.strategy import ExitRules

logger = get_logger("app.strategy_engine.api.exit_templates")

router = APIRouter(prefix="/api/templates/exit", tags=["exit-templates"])


# ─── Boundary models ───────────────────────────────────────────────────


class ExitTemplateCreate(BaseModel):
    """POST / PUT body. ``exit_rules`` is the canonical
    ``ExitRules`` shape — validated against that model before
    persistence."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2_000)
    exit_rules: dict[str, Any] = Field(...)
    indicators_used: list[dict[str, Any]] = Field(default_factory=list)


class ExitTemplateRead(BaseModel):
    """Wire shape of a stored template — what the frontend renders."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    exit_rules: dict[str, Any]
    indicators_used: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class ExitTemplateListResponse(BaseModel):
    templates: list[ExitTemplateRead]
    count: int


# ─── Helpers ───────────────────────────────────────────────────────────


def _validate_exit_shape(body: ExitTemplateCreate) -> None:
    """Run the canonical ``ExitRules`` validator over ``body.exit_rules``.

    Any malformed primitive (negative target, bad ``squareOffTime``
    pattern, unknown ``indicatorExits[].type``) raises
    ``ValidationError`` here — translated to a 422 with the first
    error message so the frontend can surface it inline. The
    ``_at_least_one_exit`` model_validator on ``ExitRules`` also
    fires here, blocking templates with no exit primitive at all.
    """
    try:
        ExitRules.model_validate(body.exit_rules)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid exit block: {first.get('msg', 'validation error')}",
        ) from exc


async def _load_owned_template(
    db: AsyncSession, user: User, template_id: uuid.UUID
) -> ExitTemplate:
    """Fetch + ownership-scope check. 404 covers both 'not found'
    and 'not yours' so the endpoint isn't an enumeration oracle."""
    stmt = select(ExitTemplate).where(
        ExitTemplate.id == template_id,
        ExitTemplate.user_id == user.id,
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
    response_model=ExitTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_exit_template(
    body: ExitTemplateCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ExitTemplateRead:
    """Persist a new exit-rule template for the calling user."""
    _validate_exit_shape(body)

    template = ExitTemplate(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        exit_rules=dict(body.exit_rules),
        indicators_used=list(body.indicators_used),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    logger.info(
        "exit_template.created",
        user_id=str(current_user.id),
        template_id=str(template.id),
        name=body.name,
    )
    return ExitTemplateRead.model_validate(template)


@router.get("", response_model=ExitTemplateListResponse)
async def list_exit_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ExitTemplateListResponse:
    """Every exit template owned by the calling user, newest first."""
    stmt = (
        select(ExitTemplate)
        .where(ExitTemplate.user_id == current_user.id)
        .order_by(ExitTemplate.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [ExitTemplateRead.model_validate(r) for r in rows]
    return ExitTemplateListResponse(templates=items, count=len(items))


@router.get("/{template_id}", response_model=ExitTemplateRead)
async def get_exit_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ExitTemplateRead:
    template = await _load_owned_template(db, current_user, template_id)
    return ExitTemplateRead.model_validate(template)


@router.put("/{template_id}", response_model=ExitTemplateRead)
async def update_exit_template(
    template_id: uuid.UUID,
    body: ExitTemplateCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ExitTemplateRead:
    """Replace the template — full PUT semantics, not partial PATCH."""
    _validate_exit_shape(body)
    template = await _load_owned_template(db, current_user, template_id)
    template.name = body.name
    template.description = body.description
    template.exit_rules = dict(body.exit_rules)
    template.indicators_used = list(body.indicators_used)
    await db.commit()
    await db.refresh(template)
    logger.info(
        "exit_template.updated",
        user_id=str(current_user.id),
        template_id=str(template.id),
    )
    return ExitTemplateRead.model_validate(template)


@router.delete(
    "/{template_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_exit_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    template = await _load_owned_template(db, current_user, template_id)
    await db.delete(template)
    await db.commit()
    logger.info(
        "exit_template.deleted",
        user_id=str(current_user.id),
        template_id=str(template_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
