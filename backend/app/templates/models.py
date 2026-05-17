"""SQLAlchemy ORM models for the Strategy Template System.

Lives in ``app.templates`` rather than ``app.db.models`` per the
Phase 1 spec — keeps all template-related code (model, schemas,
validator, registry, clone service, API) under one roof so the
new system is easy to remove or move in a future refactor without
touching :mod:`app.db.models` (which holds the long-stable core
entities).

Two tables:

    :class:`StrategyTemplate`
        The 113-entry catalog row. ``slug`` is the public stable id
        used in URLs and the seed JSON.

    :class:`StrategyTemplateOrigin`
        Linking row recording a cloned strategy's template provenance.
        Insert-only after :meth:`clone_service.clone_template`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

if TYPE_CHECKING:
    pass


class StrategyTemplate(Base):
    """Strategy template catalog row.

    Each row carries display metadata (name, description, category,
    complexity, risk_level, tags) plus an opaque ``config_json``
    payload that the future backtest engine + strategy builder will
    consume. For Phase 1, only the 15 active equity templates have a
    populated ``config_json``; everything else has the empty object
    ``{}`` and ``is_active=False``.
    """

    __tablename__ = "strategy_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    segment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    instrument_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    complexity: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    description_en: Mapped[str] = mapped_column(Text, nullable=False)
    description_hi: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    recommended_capital_inr: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    timeframe: Mapped[str] = mapped_column(
        String(16), nullable=False, default="5m"
    )
    indicators_used: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    index_filter: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    requires_options_builder: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    legs_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class StrategyTemplateOrigin(Base):
    """Linking row — records template provenance for a cloned strategy.

    Inserted by :func:`app.templates.clone_service.clone_template`.
    Never updated, never deleted directly — strategy delete cascades
    via ``strategies.id`` FK; template delete is RESTRICTed at the FK
    so trace data outlives a template removal.
    """

    __tablename__ = "strategy_template_origin"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategy_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    template_slug: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    cloned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


__all__ = ["StrategyTemplate", "StrategyTemplateOrigin"]
