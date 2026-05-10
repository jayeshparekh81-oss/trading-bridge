"""``exit_templates`` table — reusable Exit-Builder snapshots.

Mirrors :class:`EntryTemplate` for the exit half of the strategy
DSL. Stores the full ``ExitRules`` block (target / stop-loss /
trailing / partial exits / square-off time / indicator exits /
reverse-signal flag) plus the ``indicators_used`` list so the
loader can re-populate the indicator picker for templates that
reference indicator-driven exits.

Schema validation routes through ``ExitRules.model_validate`` at the
API layer — that model's own ``_at_least_one_exit`` model_validator
guarantees the persisted block always has at least one exit
primitive.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class ExitTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One saved exit-rule template owned by ``user_id``."""

    __tablename__ = "exit_templates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Full :class:`ExitRules` block as a JSON object. Keys mirror the
    #: model's camelCase aliases (``targetPercent``,
    #: ``stopLossPercent``, ``trailingStopPercent``, ``partialExits``,
    #: ``squareOffTime``, ``indicatorExits``, ``reverseSignalExit``).
    #: API layer round-trips through ``ExitRules.model_validate`` so a
    #: malformed block fails with 422 before any DB write — the
    #: ``_at_least_one_exit`` validator on that model also fires.
    exit_rules: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    #: List of :class:`IndicatorConfig` dicts referenced by the
    #: template's ``indicatorExits``. Stored as JSON (not ``text[]``)
    #: so the same ORM ships against SQLite test engines + Postgres.
    indicators_used: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    def __repr__(self) -> str:
        return (
            f"ExitTemplate(id={self.id!r}, user_id={self.user_id!r}, "
            f"name={self.name!r})"
        )


__all__ = ["ExitTemplate"]
