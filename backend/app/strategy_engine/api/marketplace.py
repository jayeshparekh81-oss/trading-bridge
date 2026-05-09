"""Marketplace API — Phase 1.

Three resource families under ``/api/marketplace``:

    * ``listings``      — creator-published strategy entries
    * ``subscriptions`` — subscriber side of the listing
    * ``ratings``       — 1-5 star + optional review

Permission gating:

    * Creating / updating / publishing / archiving a listing requires
      the ``creator`` role (or above) — :func:`require_creator_or_above`.
    * Browsing published listings is open to any authenticated user.
    * Subscribing / unsubscribing is open to any authenticated user.
    * Submitting a rating requires an *active* subscription — the
      router does the lookup itself.

Phase 1 deferrals (see commit body for details):

    * Real payment integration is stubbed — we just record
      ``amount_paid_inr = listing.price_inr`` at subscribe time as
      if the gateway had succeeded.
    * The Strategy Transparency Ledger snapshot lives in Phase 2.
    * The frontend ships in Phase 3.
    * Royalty / payout tracking lands in Phase 4.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.auth.roles import require_creator_or_above
from app.core.logging import get_logger
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_rating import MarketplaceRating
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session

logger = get_logger("app.strategy_engine.api.marketplace")

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


_LISTING_STATUSES = ("draft", "published", "suspended", "archived")
_SUBSCRIPTION_STATUSES = ("active", "cancelled", "expired")


# ─── Boundary models ───────────────────────────────────────────────────


class ListingCreate(BaseModel):
    """POST body — create a draft listing for an existing strategy
    owned by the calling creator."""

    model_config = ConfigDict(extra="forbid")

    strategy_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=10_000)
    price_inr: float = Field(default=0.0, ge=0.0, le=10_000_000.0)
    tags: list[str] = Field(default_factory=list, max_length=20)


class ListingUpdate(BaseModel):
    """PUT body — partial update of a draft / published listing.
    Status transitions go through dedicated endpoints
    (``/publish``, ``/archive``)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=10_000)
    price_inr: float | None = Field(default=None, ge=0.0, le=10_000_000.0)
    tags: list[str] | None = Field(default=None, max_length=20)


class ListingRead(BaseModel):
    """Wire shape returned by every listing endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_id: uuid.UUID
    creator_id: uuid.UUID
    title: str
    description: str
    price_inr: float
    tags: list[str]
    status: Literal["draft", "published", "suspended", "archived"]
    performance_snapshot: dict[str, Any] | None
    subscriber_count: int
    rating_avg: float | None
    rating_count: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ListingListResponse(BaseModel):
    listings: list[ListingRead]
    count: int


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    subscriber_id: uuid.UUID
    subscribed_at: datetime
    access_until: datetime | None
    status: Literal["active", "cancelled", "expired"]
    amount_paid_inr: float


class SubscriptionListResponse(BaseModel):
    subscriptions: list[SubscriptionRead]
    count: int


class RatingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(..., ge=1, le=5)
    review: str | None = Field(default=None, max_length=4_000)


class RatingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    rater_id: uuid.UUID
    rating: int
    review: str | None
    created_at: datetime
    updated_at: datetime


class RatingListResponse(BaseModel):
    ratings: list[RatingRead]
    count: int


# ─── Helpers ───────────────────────────────────────────────────────────


def _to_read(listing: MarketplaceListing) -> ListingRead:
    """Cast a SQLAlchemy ``MarketplaceListing`` into the wire shape,
    converting ``Decimal`` → ``float`` on the price + rating fields."""
    return ListingRead(
        id=listing.id,
        strategy_id=listing.strategy_id,
        creator_id=listing.creator_id,
        title=listing.title,
        description=listing.description,
        price_inr=float(listing.price_inr),
        tags=list(listing.tags),
        status=listing.status,  # type: ignore[arg-type]
        performance_snapshot=listing.performance_snapshot,
        subscriber_count=listing.subscriber_count,
        rating_avg=float(listing.rating_avg) if listing.rating_avg is not None else None,
        rating_count=listing.rating_count,
        published_at=listing.published_at,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


def _sub_to_read(sub: MarketplaceSubscription) -> SubscriptionRead:
    return SubscriptionRead(
        id=sub.id,
        listing_id=sub.listing_id,
        subscriber_id=sub.subscriber_id,
        subscribed_at=sub.subscribed_at,
        access_until=sub.access_until,
        status=sub.status,  # type: ignore[arg-type]
        amount_paid_inr=float(sub.amount_paid_inr),
    )


async def _load_listing_or_404(
    db: AsyncSession, listing_id: uuid.UUID
) -> MarketplaceListing:
    """Fetch a listing without an ownership check — for read paths."""
    listing = (
        await db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.id == listing_id
            )
        )
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )
    return listing


async def _load_owned_listing(
    db: AsyncSession, listing_id: uuid.UUID, creator: User
) -> MarketplaceListing:
    """Fetch + ownership check. 404 (not 403) on cross-creator so
    the endpoint isn't an enumeration oracle."""
    listing = (
        await db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.id == listing_id,
                MarketplaceListing.creator_id == creator.id,
            )
        )
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )
    return listing


async def _refresh_listing_rating(
    db: AsyncSession, listing: MarketplaceListing
) -> None:
    """Recompute ``rating_avg`` + ``rating_count`` for ``listing``
    from the ratings table. Called inline whenever a rating is
    inserted, updated, or deleted so the denormalised counters on
    the listing stay consistent."""
    stmt = select(
        func.count(MarketplaceRating.id),
        func.avg(MarketplaceRating.rating),
    ).where(MarketplaceRating.listing_id == listing.id)
    count, avg = (await db.execute(stmt)).one()
    listing.rating_count = int(count)
    listing.rating_avg = (
        Decimal(avg).quantize(Decimal("0.01")) if avg is not None else None
    )


# ─── Listing endpoints — creator-only mutations ───────────────────────


@router.post(
    "/listings",
    response_model=ListingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_listing(
    body: ListingCreate,
    current_user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ListingRead:
    """Create a draft listing from a strategy the creator owns."""
    strategy = (
        await db.execute(
            select(Strategy).where(
                Strategy.id == body.strategy_id,
                Strategy.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found in your account.",
        )

    listing = MarketplaceListing(
        strategy_id=body.strategy_id,
        creator_id=current_user.id,
        title=body.title,
        description=body.description,
        price_inr=Decimal(str(body.price_inr)),
        tags=list(body.tags),
        status="draft",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    logger.info(
        "marketplace.listing.created",
        listing_id=str(listing.id),
        creator_id=str(current_user.id),
    )
    return _to_read(listing)


@router.put("/listings/{listing_id}", response_model=ListingRead)
async def update_listing(
    listing_id: uuid.UUID,
    body: ListingUpdate,
    current_user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ListingRead:
    """Partial update of an owned draft / published listing.

    Suspended / archived listings are read-only — re-publish via the
    archive flow if you need to change them.
    """
    listing = await _load_owned_listing(db, listing_id, current_user)
    if listing.status not in ("draft", "published"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Listing is {listing.status} and cannot be edited. "
                "Suspended / archived listings are read-only."
            ),
        )

    if body.title is not None:
        listing.title = body.title
    if body.description is not None:
        listing.description = body.description
    if body.price_inr is not None:
        listing.price_inr = Decimal(str(body.price_inr))
    if body.tags is not None:
        listing.tags = list(body.tags)
    await db.commit()
    await db.refresh(listing)
    logger.info(
        "marketplace.listing.updated",
        listing_id=str(listing.id),
        creator_id=str(current_user.id),
    )
    return _to_read(listing)


@router.post("/listings/{listing_id}/publish", response_model=ListingRead)
async def publish_listing(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ListingRead:
    """Move a draft listing to ``published`` (visible in browse)."""
    listing = await _load_owned_listing(db, listing_id, current_user)
    if listing.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot publish a listing in status {listing.status!r}.",
        )
    listing.status = "published"
    listing.published_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(listing)
    logger.info(
        "marketplace.listing.published",
        listing_id=str(listing.id),
        creator_id=str(current_user.id),
    )
    return _to_read(listing)


@router.post("/listings/{listing_id}/archive", response_model=ListingRead)
async def archive_listing(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ListingRead:
    """Retire a listing from the marketplace. Existing subscribers
    keep their access until ``access_until`` (Phase 4 enforces this)."""
    listing = await _load_owned_listing(db, listing_id, current_user)
    if listing.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Listing is already archived.",
        )
    listing.status = "archived"
    await db.commit()
    await db.refresh(listing)
    logger.info(
        "marketplace.listing.archived",
        listing_id=str(listing.id),
        creator_id=str(current_user.id),
    )
    return _to_read(listing)


@router.get("/listings/me", response_model=ListingListResponse)
async def list_my_listings(
    current_user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ListingListResponse:
    """Every listing owned by the calling creator, regardless of
    status — drafts, published, suspended, archived."""
    rows = (
        await db.execute(
            select(MarketplaceListing)
            .where(MarketplaceListing.creator_id == current_user.id)
            .order_by(MarketplaceListing.created_at.desc())
        )
    ).scalars().all()
    items = [_to_read(r) for r in rows]
    return ListingListResponse(listings=items, count=len(items))


# ─── Listing endpoints — public browse ────────────────────────────────


@router.get("/listings", response_model=ListingListResponse)
async def browse_listings(
    _current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    tag: str | None = Query(default=None),
    max_price: float | None = Query(default=None, ge=0),
    min_rating: float | None = Query(default=None, ge=0, le=5),
) -> ListingListResponse:
    """Browse published listings with simple tag / price / rating
    filters. Suspended / archived / draft listings are excluded.

    Phase 1 ships a basic ``ORDER BY published_at DESC`` — Phase 2
    polish swaps in trust-weighted ranking + cursor pagination.
    """
    stmt = select(MarketplaceListing).where(
        MarketplaceListing.status == "published"
    )
    if max_price is not None:
        stmt = stmt.where(MarketplaceListing.price_inr <= Decimal(str(max_price)))
    if min_rating is not None:
        stmt = stmt.where(MarketplaceListing.rating_avg >= Decimal(str(min_rating)))
    stmt = stmt.order_by(MarketplaceListing.published_at.desc())

    rows = (await db.execute(stmt)).scalars().all()
    if tag is not None:
        rows = [r for r in rows if tag in (r.tags or [])]
    items = [_to_read(r) for r in rows]
    return ListingListResponse(listings=items, count=len(items))


@router.get("/listings/{listing_id}", response_model=ListingRead)
async def get_listing(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ListingRead:
    """Listing detail. Drafts are visible only to the owning creator;
    every other status is visible to any authenticated user."""
    listing = await _load_listing_or_404(db, listing_id)
    if listing.status == "draft" and listing.creator_id != current_user.id:
        # Hide drafts from non-owners; 404 instead of 403 to avoid
        # leaking the listing's existence.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )
    return _to_read(listing)


# ─── Subscription endpoints ───────────────────────────────────────────


@router.post(
    "/listings/{listing_id}/subscribe",
    response_model=SubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe_to_listing(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SubscriptionRead:
    """Subscribe to a published listing.

    Phase 1 stub-payments: the row records ``amount_paid_inr ==
    listing.price_inr`` as if the gateway had succeeded. Phase 4
    swaps in a real provider with confirmed-charge amounts.
    """
    listing = await _load_listing_or_404(db, listing_id)
    if listing.status != "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Listing status is {listing.status!r}; cannot subscribe.",
        )
    if listing.creator_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Creators cannot subscribe to their own listings.",
        )

    # Already an active subscription? Idempotent re-call returns the
    # existing row rather than violating the partial unique index.
    existing = (
        await db.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.listing_id == listing_id,
                MarketplaceSubscription.subscriber_id == current_user.id,
                MarketplaceSubscription.status == "active",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _sub_to_read(existing)

    sub = MarketplaceSubscription(
        listing_id=listing_id,
        subscriber_id=current_user.id,
        subscribed_at=datetime.now(UTC),
        status="active",
        amount_paid_inr=listing.price_inr,
    )
    db.add(sub)

    listing.subscriber_count = listing.subscriber_count + 1
    await db.commit()
    await db.refresh(sub)
    logger.info(
        "marketplace.subscription.created",
        listing_id=str(listing_id),
        subscriber_id=str(current_user.id),
        amount_paid_inr=str(sub.amount_paid_inr),
    )
    # Analytics — additive, safe-to-fail.
    from app.observability import hash_resource_id, track_event

    track_event(
        user_id=str(current_user.id),
        event_name="marketplace_subscribed",
        properties={
            "listing_id_hash": hash_resource_id("listing", str(listing_id)),
            "was_paid": float(listing.price_inr) > 0,
        },
    )
    return _sub_to_read(sub)


@router.delete(
    "/listings/{listing_id}/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unsubscribe_from_listing(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Mark the caller's active subscription as ``cancelled``.
    The row stays in the table so analytics + ratings (which require
    *was-subscribed*) keep working."""
    sub = (
        await db.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.listing_id == listing_id,
                MarketplaceSubscription.subscriber_id == current_user.id,
                MarketplaceSubscription.status == "active",
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found.",
        )
    sub.status = "cancelled"

    listing = await _load_listing_or_404(db, listing_id)
    listing.subscriber_count = max(0, listing.subscriber_count - 1)
    await db.commit()
    logger.info(
        "marketplace.subscription.cancelled",
        listing_id=str(listing_id),
        subscriber_id=str(current_user.id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subscriptions/me", response_model=SubscriptionListResponse)
async def list_my_subscriptions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SubscriptionListResponse:
    """Every subscription record belonging to the calling user — all
    statuses, newest first."""
    rows = (
        await db.execute(
            select(MarketplaceSubscription)
            .where(MarketplaceSubscription.subscriber_id == current_user.id)
            .order_by(MarketplaceSubscription.subscribed_at.desc())
        )
    ).scalars().all()
    items = [_sub_to_read(r) for r in rows]
    return SubscriptionListResponse(subscriptions=items, count=len(items))


# ─── Rating endpoints ─────────────────────────────────────────────────


async def _require_subscribed(
    db: AsyncSession, listing_id: uuid.UUID, user: User
) -> None:
    """403 if the user has no record of an active subscription to
    ``listing_id``. Cancelled subs still pass — once you've paid for
    a listing, you've earned the right to rate it."""
    sub = (
        await db.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.listing_id == listing_id,
                MarketplaceSubscription.subscriber_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only subscribers can rate this listing.",
        )


@router.post(
    "/listings/{listing_id}/ratings",
    response_model=RatingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rating(
    listing_id: uuid.UUID,
    body: RatingCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RatingRead:
    """Submit a rating for a listing the caller has subscribed to.

    Idempotent on ``(listing_id, rater_id)`` — if a rating already
    exists, returns 409 and instructs the caller to use PUT to
    update it.
    """
    listing = await _load_listing_or_404(db, listing_id)
    await _require_subscribed(db, listing_id, current_user)

    existing = (
        await db.execute(
            select(MarketplaceRating).where(
                MarketplaceRating.listing_id == listing_id,
                MarketplaceRating.rater_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You have already rated this listing. "
                "Use PUT /ratings/{rating_id} to update it."
            ),
        )

    rating = MarketplaceRating(
        listing_id=listing_id,
        rater_id=current_user.id,
        rating=body.rating,
        review=body.review,
    )
    db.add(rating)
    await db.flush()
    await _refresh_listing_rating(db, listing)
    await db.commit()
    await db.refresh(rating)
    logger.info(
        "marketplace.rating.created",
        listing_id=str(listing_id),
        rater_id=str(current_user.id),
        rating=body.rating,
    )
    # Analytics — additive, safe-to-fail.
    from app.observability import hash_resource_id, track_event

    track_event(
        user_id=str(current_user.id),
        event_name="marketplace_rated",
        properties={
            "listing_id_hash": hash_resource_id("listing", str(listing_id)),
            "rating": body.rating,
        },
    )
    return RatingRead.model_validate(rating)


@router.put(
    "/listings/{listing_id}/ratings/{rating_id}",
    response_model=RatingRead,
)
async def update_rating(
    listing_id: uuid.UUID,
    rating_id: uuid.UUID,
    body: RatingCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RatingRead:
    """Update the caller's existing rating. Only the rater can edit
    their own row — cross-user attempts get 404."""
    rating = (
        await db.execute(
            select(MarketplaceRating).where(
                MarketplaceRating.id == rating_id,
                MarketplaceRating.listing_id == listing_id,
                MarketplaceRating.rater_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if rating is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rating not found.",
        )
    rating.rating = body.rating
    rating.review = body.review

    listing = await _load_listing_or_404(db, listing_id)
    await db.flush()
    await _refresh_listing_rating(db, listing)
    await db.commit()
    await db.refresh(rating)
    logger.info(
        "marketplace.rating.updated",
        listing_id=str(listing_id),
        rater_id=str(current_user.id),
        rating=body.rating,
    )
    return RatingRead.model_validate(rating)


@router.get(
    "/listings/{listing_id}/ratings", response_model=RatingListResponse
)
async def list_listing_ratings(
    listing_id: uuid.UUID,
    _current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RatingListResponse:
    """Paginated ratings for a listing, newest first."""
    await _load_listing_or_404(db, listing_id)
    rows = (
        await db.execute(
            select(MarketplaceRating)
            .where(MarketplaceRating.listing_id == listing_id)
            .order_by(MarketplaceRating.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [RatingRead.model_validate(r) for r in rows]
    return RatingListResponse(ratings=items, count=len(items))


# Defensive — silence unused-import warnings if a refactor strips them.
_ = ValidationError


__all__ = ["router"]
