"""``paper_sessions`` table — DB persistence of paper-trading sessions.

Distinct from the Pydantic ``PaperSession`` snapshot in
:mod:`app.strategy_engine.paper_trading.models` — that one is the
in-process boundary for the streaming engine, this one is the durable
record the live-orders SafetyChain consults to count completed sessions
across restarts.

A row is created when a session starts and updated on completion. The
unique ``(user_id, strategy_id, session_date)`` constraint enforces "at
most one paper session per strategy per trading day" — the
SafetyChain's "7 completed paper sessions" gate counts distinct days,
not session restarts.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.paper_trade import PaperTrade


class PaperSession(UUIDPrimaryKeyMixin, Base):
    """One paper-trading session for one (user, strategy, day)."""

    __tablename__ = "paper_sessions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "strategy_id",
            "session_date",
            name="uq_paper_sessions_user_strategy_date",
        ),
        Index(
            "ix_paper_sessions_user_strategy_complete",
            "user_id",
            "strategy_id",
            "is_complete",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The trading-day this session belongs to. The unique constraint on
    #: ``(user_id, strategy_id, session_date)`` makes the "7 completed
    #: sessions" gate count distinct days, not session restarts.
    session_date: Mapped[date] = mapped_column(Date, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Explicit completion flag. The engine sets this on ``end_session``.
    #: Computing it from market hours would couple persistence to a
    #: trading-clock — keep it explicit, set by the caller.
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )

    total_trades: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    total_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        server_default="0",
        default=Decimal("0"),
    )

    #: Strategy-engine identifier — the ``StrategyJSON.id`` string the
    #: engine carries on the ``PaperSession`` Pydantic snapshot. Stored
    #: alongside the FK ``strategy_id`` so the in-process snapshot can be
    #: round-tripped back from a DB row when needed.
    engine_strategy_id: Mapped[str] = mapped_column(
        String(128), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trades: Mapped[list[PaperTrade]] = relationship(
        "PaperTrade",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"PaperSession(id={self.id!r}, user_id={self.user_id!r}, "
            f"strategy_id={self.strategy_id!r}, "
            f"session_date={self.session_date!r}, "
            f"is_complete={self.is_complete})"
        )


__all__ = ["PaperSession"]
