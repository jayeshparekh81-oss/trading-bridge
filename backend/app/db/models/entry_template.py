"""``entry_templates`` table — reusable Entry-Builder snapshots.

Standalone Entry Builder lets a user author one ``EntryRules`` block
in isolation and save it for later reuse. The row stores everything
needed to round-trip a template back into the builder UI:

    * ``side`` + ``operator`` — top-level entry knobs.
    * ``conditions`` — full Pydantic ``Condition`` list as JSON.
    * ``indicators_used`` — the ``IndicatorConfig`` list (JSON array)
      so the loader can re-populate the indicator catalogue panel
      alongside the condition rows.

The shape mirrors :class:`StrategyJSON.entry` but lifts it into a
top-level row keyed by ``user_id`` so templates aren't owned by any
particular strategy. Phase 2 will add a "Apply to current strategy"
action that copies the template's fields into a strategy's entry
block.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class EntryTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One saved entry-condition template owned by ``user_id``."""

    __tablename__ = "entry_templates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Top-level entry knobs. Stored as plain text rather than enums
    #: so the column is portable across the test SQLite + production
    #: Postgres without a CHECK constraint that the test harness's
    #: ``Base.metadata.create_all`` would also need to enforce.
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    operator: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="AND", default="AND"
    )

    #: Full :class:`EntryRules.conditions` list serialised as a JSON
    #: array. Each entry is one of ``IndicatorCondition``,
    #: ``CandleCondition``, ``TimeCondition``, or ``PriceCondition``
    #: per the Phase 1 strategy schema. Round-trip via the API layer
    #: validates against the canonical Pydantic union.
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    #: List of :class:`IndicatorConfig` dicts the template references.
    #: Stored as JSON (not ``text[]``) so the same ORM ships against
    #: SQLite test engines + Postgres production. Each entry is a
    #: full indicator config dict so the loader can re-populate the
    #: builder's indicator picker without a registry round-trip.
    indicators_used: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    def __repr__(self) -> str:
        return (
            f"EntryTemplate(id={self.id!r}, user_id={self.user_id!r}, "
            f"name={self.name!r})"
        )


__all__ = ["EntryTemplate"]
