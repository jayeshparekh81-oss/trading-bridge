"""``ledger_snapshots`` table — Strategy Transparency Ledger.

Append-only by convention. Every row records one trading day of a
listing's performance plus a cryptographic chain signature that
links to the prior snapshot. Application code never UPDATEs or
DELETEs these rows; the verification API walks the chain and flags
any out-of-band tampering.

Phase 4 will add a real Polygon transaction hash to each
attestation; Phase 2 stores the hash chain off-chain and the
attestation's ``polygon_tx_hash`` stays NULL.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class LedgerSnapshot(UUIDPrimaryKeyMixin, Base):
    """One day of a listing's verifiable performance."""

    __tablename__ = "ledger_snapshots"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # ─── Performance payload (frozen once written) ─────────────────────
    cumulative_pnl_inr: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0")
    )
    max_drawdown_pct: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), nullable=False, default=Decimal("0")
    )
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0")
    )
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 4), nullable=True
    )

    # ─── Forward-testing tracking ──────────────────────────────────────
    days_since_publish: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    paper_trades_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    live_trades_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # ─── Cryptographic chain ───────────────────────────────────────────
    #: SHA-256 hex digest of the canonical-JSON-serialised payload
    #: fields (everything above this comment, plus listing_id /
    #: snapshot_date / sequence_number). Recomputable from the row
    #: itself — used by the verification API to detect tampered
    #: payload columns.
    data_hash: Mapped[str] = mapped_column(Text, nullable=False)
    #: ``chain_signature`` of the previous snapshot for this
    #: listing. NULL only on the genesis snapshot.
    prior_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: SHA-256(``data_hash`` + ``"|"`` + (``prior_hash`` or ``"GENESIS"``)).
    #: This is what the next snapshot will reference as its
    #: ``prior_hash``.
    chain_signature: Mapped[str] = mapped_column(Text, nullable=False)

    # ─── Audit ─────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return (
            f"LedgerSnapshot(id={self.id!r}, "
            f"listing_id={self.listing_id!r}, "
            f"sequence={self.sequence_number}, "
            f"date={self.snapshot_date!s})"
        )


__all__ = ["LedgerSnapshot"]
