"""Pydantic v2 schemas for the Strategy Template System.

Wire shapes for the four endpoints:

    * ``GET /api/templates``               → :class:`TemplateListResponse`
    * ``GET /api/templates/{slug}``        → :class:`TemplateDetail`
    * ``POST /api/templates/{slug}/clone`` → :class:`CloneResponse`
    * ``GET /api/templates/categories``    → :class:`CategoryCounts`

All shapes are ``frozen=True, extra="forbid"`` per project convention
so unknown fields fail fast at the boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════
# Enums — match the DB CHECK constraints exactly
# ═══════════════════════════════════════════════════════════════════════


class Segment(StrEnum):
    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    COMMODITY = "COMMODITY"
    CURRENCY = "CURRENCY"


class InstrumentType(StrEnum):
    CASH = "CASH"
    FUTURES = "FUTURES"
    CALL = "CALL"
    PUT = "PUT"
    MULTI_LEG = "MULTI_LEG"


class Complexity(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ═══════════════════════════════════════════════════════════════════════
# Output shapes
# ═══════════════════════════════════════════════════════════════════════


class TemplateSummary(BaseModel):
    """Lightweight template row for catalog list responses.

    Omits ``config_json`` + verbose descriptions so the picker can
    render 100+ entries without large payloads. Detail endpoint
    returns the full :class:`TemplateDetail`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: uuid.UUID
    slug: str
    name: str
    segment: Segment
    instrument_type: InstrumentType
    category: str
    complexity: Complexity
    description_en: str = Field(
        ..., description="Plain-English one-line description"
    )
    risk_level: RiskLevel
    recommended_capital_inr: int
    timeframe: str
    indicators_used: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_active: bool
    requires_options_builder: bool
    legs_count: int | None = None
    display_order: int


class TemplateDetail(TemplateSummary):
    """Full template detail — adds Hindi description + config_json."""

    description_hi: str
    config_json: dict[str, Any] = Field(default_factory=dict)
    index_filter: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TemplateListResponse(BaseModel):
    """Body of ``GET /api/templates``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int
    active_count: int
    inactive_count: int
    items: list[TemplateSummary]


class CategoryCount(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str
    total: int
    active: int


class CategoryCounts(BaseModel):
    """Body of ``GET /api/templates/categories`` — counts per category.

    Used by the picker's filter sidebar to render the "(N)" badges
    next to each category checkbox.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[CategoryCount]


class CloneResponse(BaseModel):
    """Body of ``POST /api/templates/{slug}/clone``.

    Returns the newly-created strategy's id + name so the frontend
    can navigate the user straight to the strategy detail page.
    The template-origin link is persisted server-side; not echoed
    in the response (querying is via the linking table).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: uuid.UUID
    strategy_name: str
    template_slug: str
    message: str = Field(
        default="Strategy cloned from template — review & wire your broker."
    )


__all__ = [
    "CategoryCount",
    "CategoryCounts",
    "CloneResponse",
    "Complexity",
    "InstrumentType",
    "RiskLevel",
    "Segment",
    "TemplateDetail",
    "TemplateListResponse",
    "TemplateSummary",
]
