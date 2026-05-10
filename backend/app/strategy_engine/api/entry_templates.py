"""Entry Templates CRUD — standalone Entry Builder backend.

The standalone Entry Builder lets users author and save reusable
``EntryRules`` blocks. Endpoints (all auth-scoped to the calling
user; cross-user access returns 404 to avoid id-enumeration probes):

    POST   /api/templates/entry            create
    GET    /api/templates/entry            list (newest first)
    GET    /api/templates/entry/{id}       fetch one
    PUT    /api/templates/entry/{id}       replace
    DELETE /api/templates/entry/{id}       hard-delete

The body shape matches the ``EntryRules`` Pydantic model from the
strategy schema — ``side`` + ``operator`` + ``conditions`` — plus
``name`` / ``description`` / ``indicators_used`` for the template-
level metadata. Validation runs through
:class:`EntryRules.model_validate` so a malformed condition list
fails the request before any DB write.
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
from app.db.models.entry_template import EntryTemplate
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.schema.strategy import EntryRules

logger = get_logger("app.strategy_engine.api.entry_templates")

router = APIRouter(prefix="/api/templates/entry", tags=["entry-templates"])


# ─── Boundary models ───────────────────────────────────────────────────


class EntryTemplateCreate(BaseModel):
    """POST / PUT body. ``conditions`` is the canonical
    ``EntryRules.conditions`` shape — validated against that model
    before persistence."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2_000)
    side: str = Field(..., min_length=1, max_length=8)
    operator: str = Field(default="AND", max_length=8)
    conditions: list[dict[str, Any]] = Field(..., min_length=1)
    indicators_used: list[dict[str, Any]] = Field(default_factory=list)


class EntryTemplateRead(BaseModel):
    """Wire shape of a stored template — what the frontend renders."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    side: str
    operator: str
    conditions: list[dict[str, Any]]
    indicators_used: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class EntryTemplateListResponse(BaseModel):
    templates: list[EntryTemplateRead]
    count: int


# ─── Helpers ───────────────────────────────────────────────────────────


def _validate_entry_shape(body: EntryTemplateCreate) -> None:
    """Run the canonical ``EntryRules`` validator over ``body``.

    Any malformed condition (unknown ``type``, missing required field,
    invalid ``op``) raises ``ValidationError`` here — translated to a
    422 with the first error message so the frontend can surface it
    inline next to the offending row.
    """
    try:
        EntryRules.model_validate(
            {
                "side": body.side,
                "operator": body.operator,
                "conditions": body.conditions,
            }
        )
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid entry block: {first.get('msg', 'validation error')}",
        ) from exc


async def _load_owned_template(
    db: AsyncSession, user: User, template_id: uuid.UUID
) -> EntryTemplate:
    """Fetch + ownership-scope check. 404 covers both 'not found'
    and 'not yours' so the endpoint isn't an enumeration oracle."""
    stmt = select(EntryTemplate).where(
        EntryTemplate.id == template_id,
        EntryTemplate.user_id == user.id,
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
    response_model=EntryTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_entry_template(
    body: EntryTemplateCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> EntryTemplateRead:
    """Persist a new entry-condition template for the calling user."""
    _validate_entry_shape(body)

    template = EntryTemplate(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        side=body.side,
        operator=body.operator,
        conditions=list(body.conditions),
        indicators_used=list(body.indicators_used),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    logger.info(
        "entry_template.created",
        user_id=str(current_user.id),
        template_id=str(template.id),
        name=body.name,
    )
    return EntryTemplateRead.model_validate(template)


@router.get("", response_model=EntryTemplateListResponse)
async def list_entry_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> EntryTemplateListResponse:
    """Every entry template owned by the calling user, newest first."""
    stmt = (
        select(EntryTemplate)
        .where(EntryTemplate.user_id == current_user.id)
        .order_by(EntryTemplate.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [EntryTemplateRead.model_validate(r) for r in rows]
    return EntryTemplateListResponse(templates=items, count=len(items))


@router.get("/{template_id}", response_model=EntryTemplateRead)
async def get_entry_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> EntryTemplateRead:
    template = await _load_owned_template(db, current_user, template_id)
    return EntryTemplateRead.model_validate(template)


@router.put("/{template_id}", response_model=EntryTemplateRead)
async def update_entry_template(
    template_id: uuid.UUID,
    body: EntryTemplateCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> EntryTemplateRead:
    """Replace the template — full PUT semantics, not partial PATCH."""
    _validate_entry_shape(body)
    template = await _load_owned_template(db, current_user, template_id)
    template.name = body.name
    template.description = body.description
    template.side = body.side
    template.operator = body.operator
    template.conditions = list(body.conditions)
    template.indicators_used = list(body.indicators_used)
    await db.commit()
    await db.refresh(template)
    logger.info(
        "entry_template.updated",
        user_id=str(current_user.id),
        template_id=str(template.id),
    )
    return EntryTemplateRead.model_validate(template)


@router.delete(
    "/{template_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_entry_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    template = await _load_owned_template(db, current_user, template_id)
    await db.delete(template)
    await db.commit()
    logger.info(
        "entry_template.deleted",
        user_id=str(current_user.id),
        template_id=str(template_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
