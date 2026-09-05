"""Customer execution lane — connection state, notification ladder, connect links.

Additive only. Nothing here is read or written by the live BSE trading path.
Tokens are stored Fernet-encrypted via :mod:`app.core.security` (the helper that
already existed for ``broker_credentials``); no second crypto scheme is introduced.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class CustomerLinkStatus(str, enum.Enum):
    NEVER_CONNECTED = "NEVER_CONNECTED"
    CONNECTED = "CONNECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class LadderStep(str, enum.Enum):
    R1 = "R1"
    R2 = "R2"
    CALL = "CALL"
    RED = "RED"
    CONFIRM = "CONFIRM"


class ConnectLinkStatus(str, enum.Enum):
    ISSUED = "ISSUED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


def _enum(e, name):
    return SAEnum(e, name=name, native_enum=False,
                  values_callable=lambda o: [m.value for m in o])


class CustomerBrokerLink(UUIDPrimaryKeyMixin, Base):
    """One customer's broker connection state. The truth source for is_connected()."""

    __tablename__ = "customer_broker_link"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True, unique=True)
    broker: Mapped[str] = mapped_column(String(32), nullable=False, default="dhan")
    broker_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    access_token_enc: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_static_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proxy_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    proxy_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    proxy_password_enc: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    ip_whitelisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: When the mapped static IP was last CHANGED. Distinct from ip_whitelisted_at:
    #: that one starts Dhan's 7-day lock, this one drives the exchange's
    #: once-per-calendar-week rule. See app/domains/customer_lane/ip_lock.py.
    last_ip_change_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    status: Mapped[CustomerLinkStatus] = mapped_column(
        _enum(CustomerLinkStatus, "customer_link_status_enum"),
        nullable=False, default=CustomerLinkStatus.NEVER_CONNECTED)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CustomerNotificationLog(UUIDPrimaryKeyMixin, Base):
    """One row per (customer, step, trading_date). The UNIQUE is the anti-double-send."""

    __tablename__ = "customer_notification_log"
    __table_args__ = (
        UniqueConstraint("customer_id", "step", "trading_date",
                         name="uq_customer_notification_step_day"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    step: Mapped[LadderStep] = mapped_column(
        _enum(LadderStep, "customer_ladder_step_enum"), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class CustomerConnectLink(UUIDPrimaryKeyMixin, Base):
    """Single-use, same-day connect link. Only the HASH of the token is stored."""

    __tablename__ = "customer_connect_link"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[ConnectLinkStatus] = mapped_column(
        _enum(ConnectLinkStatus, "customer_connect_link_status_enum"),
        nullable=False, default=ConnectLinkStatus.ISSUED)


__all__ = ["CustomerBrokerLink", "CustomerNotificationLog", "CustomerConnectLink",
           "CustomerLinkStatus", "LadderStep", "ConnectLinkStatus"]
