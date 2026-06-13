"""``historical_candles`` table — persistent OHLC store for backtest realism.

Queue CCC Phase 2 skeleton (see ``docs/QUEUE_CCC_REAL_DHAN_DESIGN_v2.md``).
This is the SINGLE shared-infrastructure store for real-Dhan candles
consumed by the backtest engine, indicators (Phase 5+), and chart
history (Phase 5+). Same OHLC for every user — ``fetched_by_user_id``
is attribution-only, **not** access control.

**Composite PK** ``(symbol, exchange, timeframe, timestamp)`` lets
``INSERT … ON CONFLICT DO NOTHING`` give idempotent upserts without
uuid bloat. Every (symbol, exchange, timeframe) lookup hits
``idx_hc_lookup`` in DESC time order — match for backtest window
queries that read newest-first.

**Decimal prices.** ``Numeric(18, 4)`` keeps INR paise precision
loss-free across the bridge round-trip
(``schemas.candle.Candle`` Decimal → ORM Decimal → engine float).

**Not registered in** ``backend/app/db/models/__init__.py`` **yet.**
Phase 2 rule is additive-only (no edits to shared files). Repository
imports this module directly so SQLAlchemy registers the mapper on
first use; Alembic autogenerate won't see it until Phase 3 (or a
follow-up PATCH_INSTRUCTIONS entry adds the registration line).
Phase 2 migration is hand-written, so autogenerate is not needed.

**Future timeframe additions** (``30m``, ``4h``, ``1w``) will require
an ALTER on ``ck_hc_timeframe_enum`` — acknowledged tradeoff per
founder note 2026-06-03.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HistoricalCandle(Base):
    """One closed OHLC bar from Dhan v2 historical for a (symbol, exchange,
    timeframe, timestamp) tuple.

    Bars are **closed-only** by contract — the Phase 3 orchestrator
    filters in-progress bars before calling ``upsert_batch``. Stored
    timestamps are bar-OPEN time in UTC.

    The class deliberately does NOT inherit :class:`TimestampMixin`:
    ``created_at`` / ``updated_at`` are replaced by ``fetched_at`` which
    carries the same semantic but with provenance-aware naming. Rows are
    append-only; an ON CONFLICT DO NOTHING upsert never updates an
    existing bar, so a single timestamp is sufficient.
    """

    __tablename__ = "historical_candles"

    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )

    dhan_security_id: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'dhan_v2_historical'"),
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    fetched_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_hc_fetched_by_user",
        ),
        nullable=True,
    )
    quality_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "symbol",
            "exchange",
            "timeframe",
            "timestamp",
            name="pk_historical_candles",
        ),
        CheckConstraint("low <= high", name="ck_hc_low_le_high"),
        CheckConstraint(
            "open BETWEEN low AND high",
            name="ck_hc_open_in_range",
        ),
        CheckConstraint(
            "close BETWEEN low AND high",
            name="ck_hc_close_in_range",
        ),
        CheckConstraint("volume >= 0", name="ck_hc_volume_nonneg"),
        CheckConstraint(
            "timeframe IN ('1m','5m','15m','1h','1d')",
            name="ck_hc_timeframe_enum",
        ),
        Index(
            "idx_hc_lookup",
            "symbol",
            "exchange",
            "timeframe",
            text("timestamp DESC"),
        ),
        Index(
            "idx_hc_freshness",
            "timeframe",
            "fetched_at",
            postgresql_where=text("timeframe IN ('1m','5m','15m')"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<HistoricalCandle({self.symbol}/{self.exchange}/{self.timeframe} "
            f"@ {self.timestamp.isoformat()} c={self.close})>"
        )


__all__ = ["HistoricalCandle"]
