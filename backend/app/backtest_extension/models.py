"""SQLAlchemy 2.0 ORM models for the backtest extension.

Mirrors migration 028 (``backtest_runs`` + ``backtest_trades`` +
``backtest_metrics``). Stays out of ``app.db.models`` to match the
new-files-only doctrine — backtest extension code lives under its
own roof so future removal/relocation touches one package.

Three models:

    :class:`BacktestRun`
        One row per backtest invocation. Drives the state machine
        PENDING → RUNNING → SUCCEEDED|FAILED. Indexed by
        ``(user_id, request_hash)`` for the idempotency cache lookup;
        partial-unique on ``(user_id, request_hash) WHERE
        status='SUCCEEDED'`` enforces "one cached row per identical
        succeeded run" at the DB layer.

    :class:`BacktestTrade`
        One closed-trade audit row per Trade in BacktestResult.trades.
        FK to backtest_runs (CASCADE on delete). Unique on
        ``(run_id, trade_index)`` preserves order.

    :class:`BacktestMetrics`
        Summary stats from a SUCCEEDED run. PK = run_id (1-to-1 with
        BacktestRun). Mirrors the engine's BacktestResult metrics
        block.

Type notes:
    - Numeric columns use ``Decimal`` for precision but Pydantic
      boundary coerces to ``float`` for API responses (decision D9
      + D11 in ``DAY_1_3_DECISIONS.md``).
    - JSONB columns store dicts/lists directly; on SQLite test paths
      a ``@compiles(JSONB, "sqlite")`` shim coerces to ordinary JSON
      (decision D18).
    - ``status`` is a plain ``String(16)`` — the migration's CHECK
      constraint enforces the four valid values. Native PG ENUM was
      considered and rejected: ENUM ALTERs are expensive when adding
      a 5th status value later.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BacktestRun(Base):
    """One row per backtest invocation."""

    __tablename__ = "backtest_runs"

    # server_default=gen_random_uuid() lives on the migration (PG-only);
    # the ORM's default=uuid.uuid4 satisfies the NOT NULL constraint
    # when creating rows from Python.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SET NULL on Strategy delete — preserves backtest history (D17).
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(16), nullable=False)
    # default='PENDING' on the ORM; migration carries the PG server_default.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING"
    )
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )
    # ``none_as_null=True`` so Python ``None`` becomes SQL NULL (not the
    # JSON ``null`` literal); the CHECK constraint
    # ``(status='FAILED') = (error_json IS NOT NULL)`` distinguishes them.
    error_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships (lazy-load — keep the GET /{id} handler explicit).
    trades: Mapped[list[BacktestTrade]] = relationship(
        "BacktestTrade",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    metrics: Mapped[BacktestMetrics | None] = relationship(
        "BacktestMetrics",
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="backtest_runs_status_check",
        ),
        CheckConstraint(
            "(status IN ('SUCCEEDED', 'FAILED')) = (completed_at IS NOT NULL)",
            name="backtest_runs_completed_at_consistency",
        ),
        CheckConstraint(
            "(status = 'FAILED') = (error_json IS NOT NULL)",
            name="backtest_runs_error_consistency",
        ),
        Index(
            "ix_backtest_runs_user_id_request_hash",
            "user_id",
            "request_hash",
        ),
        # Partial index on strategy_id only when set — anonymous-config
        # runs leave strategy_id NULL.
        Index(
            "ix_backtest_runs_strategy_id",
            "strategy_id",
            postgresql_where=text("strategy_id IS NOT NULL"),
        ),
        Index(
            "ix_backtest_runs_status_started_at",
            "status",
            "started_at",
        ),
        # Idempotency guard: at most one SUCCEEDED row per
        # (user_id, request_hash). The application code does the
        # cache lookup but the DB enforces the invariant.
        Index(
            "ix_backtest_runs_user_id_hash_succeeded_uniq",
            "user_id",
            "request_hash",
            unique=True,
            postgresql_where=text("status = 'SUCCEEDED'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"BacktestRun(id={self.id!s:.8}…, status={self.status!r}, "
            f"engine={self.engine_version!r})"
        )


class BacktestTrade(Base):
    """One closed-trade audit row from a successful backtest."""

    __tablename__ = "backtest_trades"

    # server_default=gen_random_uuid() lives on the migration (PG-only);
    # the ORM's default=uuid.uuid4 satisfies the NOT NULL constraint
    # when creating rows from Python.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    trade_index: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    exit_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    exit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    pnl: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    exit_reason: Mapped[str] = mapped_column(String(128), nullable=False)
    # server_default lives on the migration (PG-only); ORM uses
    # default=list so creating an ORM instance without specifying
    # entry_reasons still satisfies the NOT NULL constraint.
    entry_reasons: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    run: Mapped[BacktestRun] = relationship(
        "BacktestRun", back_populates="trades", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint(
            "side IN ('BUY', 'SELL')",
            name="backtest_trades_side_check",
        ),
        CheckConstraint(
            "entry_price > 0 AND exit_price > 0 AND quantity > 0",
            name="backtest_trades_positive_amounts",
        ),
        UniqueConstraint(
            "run_id", "trade_index", name="uq_backtest_trades_run_index"
        ),
        Index("ix_backtest_trades_run_id", "run_id"),
    )

    def __repr__(self) -> str:
        return (
            f"BacktestTrade(run={self.run_id!s:.8}…, idx={self.trade_index}, "
            f"side={self.side}, pnl={self.pnl})"
        )


class BacktestMetrics(Base):
    """Summary stats from a SUCCEEDED run. 1-to-1 with BacktestRun."""

    __tablename__ = "backtest_metrics"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    total_pnl: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    total_return_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=6), nullable=False
    )
    win_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4), nullable=False
    )
    loss_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4), nullable=False
    )
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    average_win: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    average_loss: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    largest_win: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    largest_loss: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    max_drawdown: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4), nullable=False
    )
    # Wins-only deck → math.inf in Python; we serialise to NULL in PG.
    # Consumers treat NULL as +inf for ranking.
    profit_factor: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=6), nullable=True
    )
    expectancy: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    warnings: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    run: Mapped[BacktestRun] = relationship(
        "BacktestRun", back_populates="metrics", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint(
            "win_rate >= 0 AND win_rate <= 1",
            name="backtest_metrics_win_rate_range",
        ),
        CheckConstraint(
            "loss_rate >= 0 AND loss_rate <= 1",
            name="backtest_metrics_loss_rate_range",
        ),
        CheckConstraint(
            "max_drawdown >= 0 AND max_drawdown <= 1",
            name="backtest_metrics_max_dd_range",
        ),
        CheckConstraint(
            "total_trades >= 0",
            name="backtest_metrics_trade_count_nonneg",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"BacktestMetrics(run={self.run_id!s:.8}…, "
            f"trades={self.total_trades}, pnl={self.total_pnl})"
        )


__all__ = ["BacktestMetrics", "BacktestRun", "BacktestTrade"]
