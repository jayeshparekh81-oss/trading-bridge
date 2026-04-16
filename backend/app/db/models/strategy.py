"""``strategies`` table — user-defined strategy bindings."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class Strategy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named strategy binds a webhook token to a broker credential + limits."""

    __tablename__ = "strategies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    webhook_token_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("webhook_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    broker_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("broker_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    max_position_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allowed_symbols: Mapped[list[Any]] = mapped_column(
        JSON, default=list, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="strategies")

    def __repr__(self) -> str:
        return f"Strategy(id={self.id!r}, name={self.name!r})"


__all__ = ["Strategy"]
