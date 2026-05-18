"""``audit_logs`` — append-only security/audit trail.

Rows in this table are INSERTED only. The application never issues
UPDATE or DELETE against it; the DB role used by migrations may own the
table, but the runtime role should have INSERT/SELECT only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class ActorType(StrEnum):
    """Who produced this audit event."""

    USER = "user"
    SYSTEM = "system"
    ADMIN = "admin"


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only audit row."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor: Mapped[ActorType] = mapped_column(
        SAEnum(
            ActorType,
            name="actor_type_enum",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"AuditLog(action={self.action!r}, resource={self.resource_type!r})"


__all__ = ["ActorType", "AuditLog"]
