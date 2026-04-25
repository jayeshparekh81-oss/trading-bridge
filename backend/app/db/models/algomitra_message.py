"""``algomitra_messages`` — chat transcript log.

Phase 1A: pre-defined static chat. Phase 1B (current): real Claude
calls — assistant rows now also carry per-message token usage and INR
cost so we can audit spend per user / per day.

Rows are append-only. Content is stored as plaintext: this table holds
*conversational* text, not credentials. The widget itself warns users
not to paste API keys.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
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
    # Token usage + INR cost — populated only for assistant rows produced
    # by the Claude API path. NULL for static-flow assistant turns and
    # for all user rows.
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_creation_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_inr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(16), nullable=True)
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
