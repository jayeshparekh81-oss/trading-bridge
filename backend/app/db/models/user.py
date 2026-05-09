"""``users`` table — platform accounts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Integer, String
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

    #: Phase 2 RBAC role-vocabulary CHECK constraint. Mirrors the
    #: server-side constraint added by Migration 014 so the same
    #: rule fires under ``Base.metadata.create_all`` (test harness)
    #: and under a real Alembic upgrade. Kept on the model rather
    #: than only in the migration so a stray ``user.role = "junk"``
    #: in production code is caught at ORM-flush time, not just at
    #: insert time on the live DB.
    #
    #: ``Base.metadata.naming_convention`` (see ``app/db/base.py``)
    #: prepends ``ck_users_`` to the ``name=`` we pass here, so the
    #: final constraint name resolves to ``ck_users_role_valid``.
    #: Migration 014 spells out the full name because Alembic ops
    #: don't apply the naming convention to ``create_check_constraint``.
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'pro_user', 'creator', 'admin', 'super_admin')",
            name="role_valid",
        ),
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Phase 1 RBAC role string (migration 013). Today's two values are
    #: ``"user"`` (default) and ``"admin"``. Phase 2 extends to
    #: ``pro_user`` / ``creator`` / ``super_admin`` per the locked
    #: launch plan; the column type is ``text`` rather than an Enum so
    #: that extension doesn't require a migration. Kept in sync with
    #: ``is_admin`` at-rest via the migration backfill — Phase 2
    #: collapses ``is_admin`` into a derived property over ``role``.
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="user",
        default="user",
        index=True,
    )
    #: Per-user opt-in for live (real-money) order placement. Both this
    #: column AND the global ``LIVE_TRADING_ENABLED`` feature flag must
    #: be true for the live-orders SafetyChain to allow a place call —
    #: see :mod:`app.strategy_engine.feature_flags.user_flags`. Default
    #: is ``False`` so a fresh row, a backfill, or a forgotten admin
    #: review can never accidentally enable live trading.
    live_trading_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    # ─── Phase 13 onboarding (migration 021) ──────────────────────────
    #
    # 0 = not started, 1-5 = active step, 6 = complete. Existing
    # rows backfilled to ``6`` by the migration so they pass
    # through the dashboard's auto-redirect untouched. New signups
    # set ``onboarding_step=0`` explicitly at insert time so the
    # 5-step flow fires.
    onboarding_step: Mapped[int] = mapped_column(
        Integer, default=6, server_default="6", nullable=False
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    # ─── Phase 2 RBAC role-hierarchy accessors (additive) ─────────────
    # Read ``self.role`` rather than the legacy ``self.is_admin`` flag.
    # Mirrors the ``is_*_or_above`` helpers in
    # :mod:`app.auth.roles` so model-side and dep-side checks share
    # one truth source. Phase 1's ``is_admin`` Mapped column stays
    # untouched for backwards compatibility — Phase 3 collapses it
    # into a derived property once the existing
    # ``app.api.deps.get_current_admin`` callers migrate.

    @property
    def is_pro_or_above(self) -> bool:
        """True for ``pro_user`` and every higher-tier role on the
        write track + the parallel admin track."""
        return self.role in (
            "pro_user",
            "creator",
            "admin",
            "super_admin",
        )

    @property
    def is_creator_or_above(self) -> bool:
        """True for ``creator`` plus the admin track."""
        return self.role in ("creator", "admin", "super_admin")

    @property
    def is_super_admin(self) -> bool:
        """True only for ``super_admin``."""
        return self.role == "super_admin"


__all__ = ["User"]
