"""``indicator_status_overrides`` — admin-controlled lifecycle overrides.

The indicator registry (``INDICATOR_REGISTRY`` in
:mod:`app.strategy_engine.indicators.registry`) declares each
indicator's *default* lifecycle status. This table layers on
admin-approved overrides so an indicator can be promoted from
``coming_soon`` to ``active`` without a code deploy + migration —
critical for "we shipped the calculation but a senior trader still
needs to bless it" launch-readiness.

Effective status is the latest **non-expired** row for an
indicator id (filter ``effective_from <= now() AND
(effective_until IS NULL OR effective_until > now())``, then take
the row with the largest ``effective_from``). When no rows match,
the registry default applies.

The history-style schema (rather than a ``current_status`` flag)
gives the audit log + the admin "history" view for free — every
override change is a new row, never an update.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IndicatorStatusOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One historical override row.

    Lifecycle is append-only — a "rollback" is a *new* row with
    the desired status, not an update of the previous row. This
    keeps the audit chain trivially provable: every state the
    indicator was ever in has its own row with its own
    ``approved_by_user_id`` + ``approved_at``.
    """

    __tablename__ = "indicator_status_overrides"

    indicator_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )

    #: One of: ``active``, ``coming_soon``, ``experimental``,
    #: ``deprecated``. ``deprecated`` is new in this table —
    #: the registry's ``IndicatorStatus`` enum doesn't include
    #: it because deprecation is an admin-action concept, not a
    #: native registry lifecycle. CHECK constraint at the
    #: migration layer pins the allowed values.
    override_status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )

    override_reason: Mapped[str] = mapped_column(Text, nullable=False)

    approved_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_at: Mapped[datetime] = mapped_column(nullable=False)

    #: Window during which this override is in effect. ``effective_until``
    #: NULL means "indefinite" — the override applies until a later
    #: row supersedes it.
    effective_from: Mapped[datetime] = mapped_column(nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(nullable=True)

    #: For audit + UI — what the status was *before* this row.
    #: Either a registry default value or the prior override's
    #: ``override_status``. ``prior_status_source`` disambiguates.
    prior_status: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    prior_status_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        doc="``registry_default`` or ``prior_override``.",
    )

    #: Optional cross-reference to a row in the audit_logs table.
    #: We record overrides via the audit module separately (so
    #: read paths that scan audit_logs see them); this field
    #: lets the admin UI link back to the canonical audit entry.
    audit_log_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audit_logs.id", ondelete="SET NULL"),
        nullable=True,
    )

    #: Free-form metadata (usage stats snapshot at decision time,
    #: requesting creator's note, etc.). Read by the admin history
    #: view; opaque to the resolver.
    decision_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    def __repr__(self) -> str:
        return (
            f"IndicatorStatusOverride(id={self.id!r}, "
            f"indicator_id={self.indicator_id!r}, "
            f"override_status={self.override_status!r})"
        )


__all__ = ["IndicatorStatusOverride"]
