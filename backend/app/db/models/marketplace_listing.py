"""``marketplace_listings`` table — published-strategy catalogue rows.

One row per strategy a creator wants to expose to other users.
Lifecycle: ``draft`` → ``published`` (visible in browse) → optionally
``suspended`` (admin action) or ``archived`` (creator-driven retire).

Caching choices:

    * ``performance_snapshot`` (JSONB) holds a cached Trust + Truth +
      headline backtest stats blob so the browse endpoint doesn't
      re-run the engine for every page-view. Refresh strategy lives
      in Phase 2 alongside the Strategy Transparency Ledger
      integration.
    * ``subscriber_count`` and ``rating_avg`` / ``rating_count`` are
      denormalised counters maintained by the API layer so the browse
      list-by-rating query stays index-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MarketplaceListing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One marketplace listing — a strategy a creator has published
    (or is preparing to publish)."""

    __tablename__ = "marketplace_listings"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    #: Stored as Decimal for paise-precision; serialised as float at
    #: the API boundary (Pydantic round-trip).
    price_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )

    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    #: Lifecycle. CHECK constraint at the migration layer pins the
    #: allowed values.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft"
    )

    #: Cached Trust + Truth + headline backtest metrics. Refreshed by
    #: Phase 2's snapshot job; for now the API layer treats it as an
    #: opaque blob.
    performance_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    subscriber_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    rating_avg: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    rating_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    published_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return (
            f"MarketplaceListing(id={self.id!r}, "
            f"creator_id={self.creator_id!r}, status={self.status!r}, "
            f"title={self.title!r})"
        )


__all__ = ["MarketplaceListing"]
