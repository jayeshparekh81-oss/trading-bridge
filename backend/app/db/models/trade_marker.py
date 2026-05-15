"""``trade_markers`` table — persisted strategy entry/exit events (Phase A).

Phase A is the future write-side for strategy markers across all three
execution modes (BACKTEST, PAPER, LIVE). Today, paper-mode markers are
**derived on-read** from :class:`app.db.models.paper_trade.PaperTrade`
rows via :mod:`app.services.chart_marker_service`. That path stays
untouched — Phase A introduces a parallel, *persistent* write path so
backtests and live executions can also surface markers on the chart.

Phase B+ will migrate the read path (``app.api.chart_markers``) to
consume from this table, at which point the legacy paper-trade
derivation can be retired.

Taxonomy (two orthogonal axes — both required for a clean wire shape):

    side enum (REQUIRED on every row)
        LONG_ENTRY  — opened a long position
        LONG_EXIT   — closed a long position
        SHORT_ENTRY — opened a short position
        SHORT_EXIT  — closed a short position

    exit_reason enum (NULLABLE; populated only on *_EXIT rows)
        SIGNAL       — strategy signalled flat / reverse
        STOP_LOSS    — SL fired (hard or trailing)
        TAKE_PROFIT  — TP / target hit
        MANUAL       — user squared off via UI
        SQUARE_OFF   — end-of-session auto squareoff
        EXPIRY       — option/future expiry close

This separation lets the chart pick arrow direction from ``side`` and
the tooltip label from ``exit_reason`` without burying classification
data inside the ``signal_metadata`` JSONB column.

Idempotency
    A partial unique index over
    ``(strategy_id, side, price, date_trunc('second', timestamp_utc))``
    guarantees that a retried emit within the same wall-clock second
    cannot insert a duplicate row. The service layer catches the
    resulting ``IntegrityError`` and treats it as a no-op.

Storage choices
    * String + CHECK constraints over native PG ENUM types — same
      pattern as migrations 014 / 024. CHECK constraints round-trip
      through SQLite under ``Base.metadata.create_all`` for tests.
    * ``Numeric(20, 8)`` for ``price`` and ``pnl`` — never Float. P&L
      arithmetic loses cents under Float precision.
    * ``DateTime(timezone=True)`` for ``timestamp_utc`` — every
      timestamp in this project is tz-aware (see ``app.db.base``).
    * Self-referential FK on ``linked_marker_id`` with ``ON DELETE SET
      NULL`` so deleting an entry row doesn't cascade-delete its exit
      row; the exit just loses its link.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


# ─── Enums (Python-side; DB enforces via CHECK constraints) ────────────


class MarkerSide(StrEnum):
    """Position-event taxonomy. Every marker row carries exactly one."""

    LONG_ENTRY = "LONG_ENTRY"
    LONG_EXIT = "LONG_EXIT"
    SHORT_ENTRY = "SHORT_ENTRY"
    SHORT_EXIT = "SHORT_EXIT"

    @classmethod
    def is_entry(cls, side: "MarkerSide | str") -> bool:
        """``True`` if the side opens a position (``LONG_ENTRY`` /
        ``SHORT_ENTRY``)."""
        return str(side) in (cls.LONG_ENTRY.value, cls.SHORT_ENTRY.value)

    @classmethod
    def is_exit(cls, side: "MarkerSide | str") -> bool:
        """``True`` if the side closes a position."""
        return str(side) in (cls.LONG_EXIT.value, cls.SHORT_EXIT.value)


class MarkerMode(StrEnum):
    """Execution mode the marker was produced in."""

    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE = "LIVE"


class MarkerExitReason(StrEnum):
    """Why the position was closed. ``None`` on entry markers."""

    SIGNAL = "SIGNAL"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    MANUAL = "MANUAL"
    SQUARE_OFF = "SQUARE_OFF"
    EXPIRY = "EXPIRY"


_SIDE_VALUES = ", ".join(f"'{m.value}'" for m in MarkerSide)
_MODE_VALUES = ", ".join(f"'{m.value}'" for m in MarkerMode)
_EXIT_REASON_VALUES = ", ".join(f"'{m.value}'" for m in MarkerExitReason)


# ─── Table ─────────────────────────────────────────────────────────────


class TradeMarker(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One persisted entry or exit event on a strategy timeline."""

    __tablename__ = "trade_markers"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Self-FK. ``ON DELETE SET NULL`` so deleting an entry doesn't
    #: cascade-delete its exit; the exit just loses its link.
    linked_marker_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trade_markers.id", ondelete="SET NULL"),
        nullable=True,
    )

    #: Realised P&L for exit markers. ``None`` on entries.
    pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )

    #: Optional exit classification — only populated on ``*_EXIT`` rows.
    exit_reason: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )

    #: Free-form snapshot — broker_order_id, indicator_snapshot,
    #: raw_payload, notes, plus any forward-compatible fields. The
    #: Pydantic ``SignalMetadata`` schema validates the *known* keys
    #: with ``extra="allow"`` so unknown fields round-trip safely.
    #: ``JSON`` (not ``JSONB``) in the ORM so SQLite test engine accepts
    #: it; migration uses Postgres JSONB at rest.
    signal_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False, server_default="{}"
    )

    __table_args__ = (
        # ── Enum-validation CHECK constraints ──
        CheckConstraint(
            f"side IN ({_SIDE_VALUES})",
            name="side_valid",
        ),
        CheckConstraint(
            f"mode IN ({_MODE_VALUES})",
            name="mode_valid",
        ),
        CheckConstraint(
            (
                "exit_reason IS NULL OR exit_reason IN ("
                f"{_EXIT_REASON_VALUES})"
            ),
            name="exit_reason_valid",
        ),
        # ── Co-axis CHECK: exit_reason only on EXIT rows ──
        CheckConstraint(
            (
                "(exit_reason IS NULL) OR "
                "(side IN ('LONG_EXIT', 'SHORT_EXIT'))"
            ),
            name="exit_reason_only_on_exit",
        ),
        # ── Co-axis CHECK: pnl only on EXIT rows ──
        CheckConstraint(
            "(pnl IS NULL) OR (side IN ('LONG_EXIT', 'SHORT_EXIT'))",
            name="pnl_only_on_exit",
        ),
        # ── Co-axis CHECK: quantity > 0 ──
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("price > 0", name="price_positive"),
        # ── Composite read indexes ──
        Index(
            "ix_trade_markers_strategy_id_timestamp_utc",
            "strategy_id",
            "timestamp_utc",
        ),
        Index(
            "ix_trade_markers_user_id_symbol_mode",
            "user_id",
            "symbol",
            "mode",
        ),
        # NOTE: the idempotency partial unique index over
        # ``(strategy_id, side, price, date_trunc('second',
        # timestamp_utc))`` is declared in migration 025 only — not
        # here — because ``date_trunc`` is Postgres-specific and would
        # break the SQLite test harness's ``Base.metadata.create_all``.
        # Service-layer ``_find_dedup_row`` reproduces the 1-second
        # window in Python for both engines.
    )

    def __repr__(self) -> str:
        return (
            f"TradeMarker(id={self.id!r}, strategy_id={self.strategy_id!r}, "
            f"side={self.side!r}, ts={self.timestamp_utc!r})"
        )


__all__ = [
    "MarkerExitReason",
    "MarkerMode",
    "MarkerSide",
    "TradeMarker",
]
