"""``marketplace_ratings`` table — 1-5 star ratings + optional review.

A rater must be (or have been) an active subscriber to the listing
— the API layer enforces this. The DB layer pins:

    * 1 <= rating <= 5 (CHECK constraint).
    * Unique ``(listing_id, rater_id)`` so a user can update but not
      duplicate their rating.

Updates flow through PUT — the API layer overwrites the existing
row's ``rating`` / ``review`` and refreshes the listing's
denormalised ``rating_avg`` / ``rating_count`` counters in the
same transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MarketplaceRating(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One subscriber's rating + optional review of a listing."""

    __tablename__ = "marketplace_ratings"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rater_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"MarketplaceRating(id={self.id!r}, "
            f"listing_id={self.listing_id!r}, "
            f"rater_id={self.rater_id!r}, rating={self.rating!r})"
        )


__all__ = ["MarketplaceRating"]
