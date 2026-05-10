"""``risk_templates`` table — reusable Risk-Builder snapshots.

Mirrors :class:`EntryTemplate` / :class:`ExitTemplate` for the
risk-management half of the strategy DSL. Stores the full
``RiskRules`` block (max daily loss %, max trades / day, max loss
streak, max capital per trade %) as a JSON object.

Risk doesn't reference indicators, so unlike Entry / Exit there's
no ``indicators_used`` column.

Schema validation routes through ``RiskRules.model_validate`` at
the API layer — that model's ``gt=0`` / ``le=100`` field
constraints are the source of truth.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RiskTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One saved risk-management template owned by ``user_id``."""

    __tablename__ = "risk_templates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Full :class:`RiskRules` block as a JSON object. Keys mirror
    #: the model's camelCase aliases (``maxDailyLossPercent``,
    #: ``maxTradesPerDay``, ``maxLossStreak``,
    #: ``maxCapitalPerTradePercent``). API layer round-trips through
    #: ``RiskRules.model_validate`` so any malformed value (negative,
    #: >100 cap %, non-int integer fields) fails with 422 before any
    #: DB write.
    risk_rules: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    def __repr__(self) -> str:
        return (
            f"RiskTemplate(id={self.id!r}, user_id={self.user_id!r}, "
            f"name={self.name!r})"
        )


__all__ = ["RiskTemplate"]
