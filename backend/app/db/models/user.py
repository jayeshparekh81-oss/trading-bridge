"""``users`` table — platform accounts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.broker_credential import BrokerCredential
    from app.db.models.kill_switch import KillSwitchConfig
    from app.db.models.strategy import Strategy
    from app.db.models.webhook_token import WebhookToken


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Platform user — owns credentials, strategies, trades, and limits."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    broker_credentials: Mapped[list[BrokerCredential]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    webhook_tokens: Mapped[list[WebhookToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    strategies: Mapped[list[Strategy]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    kill_switch_config: Mapped[KillSwitchConfig | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"


__all__ = ["User"]
