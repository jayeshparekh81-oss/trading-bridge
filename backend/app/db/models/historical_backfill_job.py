"""``historical_backfill_jobs`` table — Queue CCC Phase 3 skeleton.

Tracks one outstanding (symbol, exchange, timeframe, window) backfill
request: who asked for it, when, what its current status is, and how
many bars actually landed in ``historical_candles`` when it finished.

Why a jobs table rather than ad-hoc Celery args:
    * Survives worker restarts — pending jobs are recoverable from the
      DB after the box reboots, no Redis-only state at risk.
    * The 22-symbol Phase 3 seed is just a bulk INSERT into this table;
      execution decoupled from enqueue.
    * Audit trail: ``quota_rationale_at_start`` records which
      :mod:`rate_limit_guard` branch authorised the run, so post-mortem
      "why did this gulp our live quota?" questions have a paper trail.

Migration: ``030_historical_backfill_jobs.py`` — **file-only tonight**
(per overnight brief hard-stop #3). Founder applies it in the morning
window before Phase 3 orchestrator can use this layer for real.

Not registered in :mod:`backend/app/db/models/__init__.py` — same
additive-only discipline as :class:`HistoricalCandle`. Repository
imports the module directly so SQLAlchemy registers the mapper.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Status state machine (also enforced by the DB CHECK constraint).
STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_FAILED = "FAILED"

ALL_STATUSES: tuple[str, ...] = (
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    STATUS_FAILED,
)


class HistoricalBackfillJob(Base):
    """One row per Dhan backfill request — full lifecycle persisted."""

    __tablename__ = "historical_backfill_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    dhan_security_id: Mapped[str] = mapped_column(Text, nullable=False)

    from_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{STATUS_PENDING}'"),
    )

    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_hbj_requested_by_user",
        ),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candles_inserted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    error_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Audit: which rate_limit_guard branch (off_market / market_hours_live
    # / kill_switch_paused_live_strategy) authorised the run. Populated
    # at mark_running() time so a later "why did this run during market
    # hours?" investigation has the answer in the row itself.
    quota_rationale_at_start: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in ALL_STATUSES)})",
            name="ck_hbj_status_enum",
        ),
        CheckConstraint(
            "timeframe IN ('1m','5m','15m','1h','1d')",
            name="ck_hbj_timeframe_enum",
        ),
        CheckConstraint("from_ts <= to_ts", name="ck_hbj_window_ordered"),
        CheckConstraint(
            "(status = 'PENDING') = (started_at IS NULL)",
            name="ck_hbj_started_at_consistency",
        ),
        CheckConstraint(
            "(status IN ('SUCCEEDED', 'FAILED')) = (completed_at IS NOT NULL)",
            name="ck_hbj_completed_at_consistency",
        ),
        CheckConstraint(
            "(status = 'FAILED') = (error_json IS NOT NULL)",
            name="ck_hbj_error_json_consistency",
        ),
        Index(
            "ix_hbj_status_requested_at",
            "status",
            "requested_at",
        ),
        Index(
            "ix_hbj_symbol_window",
            "symbol",
            "exchange",
            "timeframe",
            "from_ts",
            "to_ts",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover — trivial
        return (
            f"<HistoricalBackfillJob({self.symbol}/{self.exchange}/"
            f"{self.timeframe} {self.from_ts.isoformat()}→"
            f"{self.to_ts.isoformat()} {self.status})>"
        )


__all__ = [
    "ALL_STATUSES",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_RUNNING",
    "STATUS_SUCCEEDED",
    "HistoricalBackfillJob",
]
