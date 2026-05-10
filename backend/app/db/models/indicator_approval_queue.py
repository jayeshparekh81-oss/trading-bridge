"""``indicator_approval_queue`` — pending requests for status changes.

Creators (or admins) file a request to promote a ``coming_soon``
indicator to ``active`` or to deprecate an active indicator. An
admin reviews + decides; the decision row references this queue
item (and, when approved, creates a corresponding row in
``indicator_status_overrides``).

Uniqueness on ``(indicator_id, status='pending')`` is enforced at
the **service layer** rather than via a partial unique index —
SQLite (used in tests) doesn't support partial indexes cleanly,
and the service layer is the right place anyway because it can
return a meaningful 409 to the caller instead of a raw IntegrityError.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IndicatorApprovalQueue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One pending / closed request to change an indicator's status."""

    __tablename__ = "indicator_approval_queue"

    indicator_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )

    #: ``active`` (most common — promote a coming_soon)
    #: or ``deprecated`` (retire an active indicator).
    requested_status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )

    request_reason: Mapped[str] = mapped_column(Text, nullable=False)

    requester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    #: Free-form context: usage counts at request time, the
    #: requester's evidence, sample strategy ids that exercise
    #: the indicator. Opaque to the queue logic; rendered by the
    #: admin UI.
    request_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    #: Lifecycle: ``pending`` → ``approved`` / ``rejected`` /
    #: ``withdrawn``. CHECK constraint at the migration layer.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )

    decision_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: When approved, points at the override row this decision
    #: created. NULL otherwise.
    resulting_override_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "indicator_status_overrides.id", ondelete="SET NULL"
        ),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"IndicatorApprovalQueue(id={self.id!r}, "
            f"indicator_id={self.indicator_id!r}, "
            f"requested_status={self.requested_status!r}, "
            f"status={self.status!r})"
        )


__all__ = ["IndicatorApprovalQueue"]
