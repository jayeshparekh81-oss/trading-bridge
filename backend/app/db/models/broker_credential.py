"""``broker_credentials`` table — encrypted per-user broker sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.schemas.broker import BrokerName

if TYPE_CHECKING:
    from app.db.models.user import User


class BrokerCredential(UUIDPrimaryKeyMixin, Base):
    """Fernet-encrypted broker credentials for one user.

    Every ``*_enc`` column stores a Fernet token — never plaintext.
    Decryption happens in the service layer via
    :func:`app.core.security.decrypt_credential`.
    """

    __tablename__ = "broker_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_name: Mapped[BrokerName] = mapped_column(
        SAEnum(
            BrokerName,
            name="broker_name_enum",
            native_enum=False,
            # Validate against enum VALUES (lowercase) to match the DB
            # column data + CHECK constraint. Default would use the enum
            # NAMES (uppercase) — that's the bug we're fixing.
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    client_id_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    api_key_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    api_secret_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    access_token_enc: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    totp_secret_enc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="broker_credentials")

    def __repr__(self) -> str:
        return (
            f"BrokerCredential(id={self.id!r}, user_id={self.user_id!r}, "
            f"broker={self.broker_name!r})"
        )


__all__ = ["BrokerCredential"]
