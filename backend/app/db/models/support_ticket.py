"""``support_tickets`` table — customer-support ticket records.

Append-and-update by convention. Status transitions through the
admin endpoint update ``updated_at`` and (for ``resolved``)
``resolved_at``. ``assigned_admin_id`` flips when an admin
claims or reassigns a ticket; the FK is ``SET NULL`` so an
admin leaving the team unassigns gracefully.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SupportTicket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One customer-support ticket."""

    __tablename__ = "support_tickets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: One of ``bug`` / ``billing`` / ``broker_connection`` /
    #: ``strategy_help`` / ``account`` / ``other``. CHECK constraint
    #: at the migration layer pins the values.
    category: Mapped[str] = mapped_column(String(32), nullable=False)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    #: Lifecycle. CHECK-constrained — ``open`` (initial),
    #: ``in_progress`` (admin claimed), ``awaiting_user`` (admin
    #: replied, waiting on the user), ``resolved`` (closed
    #: cleanly), ``closed`` (closed without resolution).
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open"
    )

    #: Auto-set on creation by ``_priority_for_category`` in the
    #: support router; admin can override via PUT.
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium"
    )

    #: Attachment URIs / filenames. Phase 1 doesn't ship file
    #: upload — list stays empty until a future phase adds the
    #: storage path. JSON list of strings.
    attachments: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )

    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    assigned_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"SupportTicket(id={self.id!r}, user_id={self.user_id!r}, "
            f"category={self.category!r}, status={self.status!r})"
        )


__all__ = ["SupportTicket"]
