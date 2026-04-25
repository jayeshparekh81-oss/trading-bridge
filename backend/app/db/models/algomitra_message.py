"""``algomitra_messages`` — chat transcript log.

Phase 1A is a pre-defined static chat. Logging every message lets us
analyse common questions, refine FAQs, and seed the Phase 1B Claude
retriever with real user phrasing.

Rows are append-only. Content is stored as plaintext: this table holds
*conversational* text, not credentials. The widget itself warns users
not to paste API keys.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class AlgoMitraRole(StrEnum):
    """Who authored a message in the AlgoMitra transcript."""

    USER = "user"
    ASSISTANT = "assistant"


class AlgoMitraMessage(UUIDPrimaryKeyMixin, Base):
    """One message in a user's AlgoMitra chat session."""

    __tablename__ = "algomitra_messages"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    role: Mapped[AlgoMitraRole] = mapped_column(
        SAEnum(AlgoMitraRole, name="algomitra_role_enum", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    flow_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    flow_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_image: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"AlgoMitraMessage(id={self.id!r}, role={self.role!r}, "
            f"session={self.session_id!r})"
        )


__all__ = ["AlgoMitraMessage", "AlgoMitraRole"]
