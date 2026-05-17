"""FastAPI routes for the Strategy Template System.

Four endpoints under ``/api/templates``:

    GET    /api/templates                  — filtered list
    GET    /api/templates/categories       — category counts
    GET    /api/templates/{slug}           — detail
    POST   /api/templates/{slug}/clone     — materialise as Strategy

All endpoints require authentication. Catalog reads are not rate-
limited beyond the standard project middleware. Clone writes
inherit the existing per-route auth + audit pattern via
``get_current_active_user``.

Wiring: add to ``backend/app/main.py``::

    from app.templates.api import router as strategy_templates_router
    app.include_router(strategy_templates_router)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models.user import User
from app.db.session import get_session
from app.templates.clone_service import (
    TemplateNotCloneableError,
    TemplateNotFoundError,
    clone_template,
)
from app.templates.models import StrategyTemplate
from app.templates.registry import (
    category_counts,
    get_template_by_slug,
    list_templates,
)
from app.templates.schemas import (
    CategoryCount,
    CategoryCounts,
    CloneResponse,
    TemplateDetail,
    TemplateListResponse,
    TemplateSummary,
)
from app.templates.validator import TemplateConfigError


router = APIRouter(
    prefix="/api/templates",
    tags=["strategy-templates"],
)


def _row_to_summary(row: StrategyTemplate) -> TemplateSummary:
    return TemplateSummary(
        id=row.id,
        slug=row.slug,
        name=row.name,
        segment=row.segment,
        instrument_type=row.instrument_type,
        category=row.category,
        complexity=row.complexity,
        description_en=row.description_en,
        risk_level=row.risk_level,
        recommended_capital_inr=row.recommended_capital_inr,
        timeframe=row.timeframe,
        indicators_used=list(row.indicators_used or []),
        tags=list(row.tags or []),
        is_active=row.is_active,
        requires_options_builder=row.requires_options_builder,
        legs_count=row.legs_count,
        display_order=row.display_order,
    )


def _row_to_detail(row: StrategyTemplate) -> TemplateDetail:
    return TemplateDetail(
        id=row.id,
        slug=row.slug,
        name=row.name,
        segment=row.segment,
        instrument_type=row.instrument_type,
        category=row.category,
        complexity=row.complexity,
        description_en=row.description_en,
        description_hi=row.description_hi,
        config_json=dict(row.config_json or {}),
        risk_level=row.risk_level,
        recommended_capital_inr=row.recommended_capital_inr,
        timeframe=row.timeframe,
        indicators_used=list(row.indicators_used or []),
        index_filter=list(row.index_filter or []),
        tags=list(row.tags or []),
        is_active=row.is_active,
        requires_options_builder=row.requires_options_builder,
        legs_count=row.legs_count,
        display_order=row.display_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ─── GET /api/templates ────────────────────────────────────────────────


@router.get(
    "",
    response_model=TemplateListResponse,
    summary="List strategy templates (filterable)",
)
async def list_route(
    category: str | None = Query(default=None),
    complexity: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=128),
    is_active: bool | None = Query(default=None),
    user: User = Depends(get_current_active_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_session),
) -> TemplateListResponse:
    """Returns the catalog filtered by the query params.

    Auth gates the endpoint (catalog metadata is not sensitive, but
    we don't want anonymous scraping). Ordering: active templates
    first, then by ``display_order`` ascending.
    """
    rows = await list_templates(
        db,
        category=category,
        complexity=complexity,
        segment=segment,
        search=search,
        is_active=is_active,
    )
    summaries = [_row_to_summary(r) for r in rows]
    active = sum(1 for r in rows if r.is_active)
    return TemplateListResponse(
        total=len(rows),
        active_count=active,
        inactive_count=len(rows) - active,
        items=summaries,
    )


# ─── GET /api/templates/categories ─────────────────────────────────────


@router.get(
    "/categories",
    response_model=CategoryCounts,
    summary="Per-category counts for the picker filter sidebar",
)
async def categories_route(
    user: User = Depends(get_current_active_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_session),
) -> CategoryCounts:
    rows = await category_counts(db)
    return CategoryCounts(
        items=[
            CategoryCount(category=cat, total=total, active=active)
            for (cat, total, active) in rows
        ]
    )


# ─── GET /api/templates/{slug} ─────────────────────────────────────────


@router.get(
    "/{slug}",
    response_model=TemplateDetail,
    summary="Full template detail (including config_json)",
)
async def detail_route(
    slug: str,
    user: User = Depends(get_current_active_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_session),
) -> TemplateDetail:
    row = await get_template_by_slug(db, slug)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {slug!r}",
        )
    return _row_to_detail(row)


# ─── POST /api/templates/{slug}/clone ──────────────────────────────────


class CloneRequest(BaseModel):
    """Optional payload for the clone endpoint.

    Currently supports a custom ``name`` for the cloned strategy.
    Future fields (e.g. ``param_overrides``) land here without
    breaking the URL contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str | None = Field(
        default=None,
        max_length=128,
        description="Override the cloned strategy's name. "
        "Defaults to ``<Template name> (from template)``.",
    )


@router.post(
    "/{slug}/clone",
    response_model=CloneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a template into a new user-owned strategy",
)
async def clone_route(
    slug: str,
    body: CloneRequest | None = None,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> CloneResponse:
    """Materialises a :class:`Strategy` from a catalog template.

    Status codes:
        * 201 — strategy created; returns id + name + template slug.
        * 404 — template slug not found.
        * 409 — template is cataloged but ``is_active=False``.
        * 501 — template requires the options builder (Phase 7-8).
        * 500 — catalog row has malformed ``config_json`` (data
          integrity issue; should not happen post-seed validation).
    """
    try:
        strategy, template = await clone_template(
            db,
            user,
            slug,
            name_override=body.name if body else None,
        )
    except TemplateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except TemplateNotCloneableError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=exc.message,
        ) from exc
    except TemplateConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Template config is malformed — contact support. "
                f"Slug: {slug!r}, reason: {exc}"
            ),
        ) from exc

    await db.commit()

    return CloneResponse(
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        template_slug=template.slug,
    )


__all__ = ["router"]
