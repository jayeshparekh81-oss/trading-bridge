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
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
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
from app.services import razorpay_billing
from app.services.razorpay_client import RazorpayConfigError, razorpay_configured

logger = get_logger("app.strategy_engine.api.marketplace")

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


_LISTING_STATUSES = ("draft", "published", "suspended", "archived")
#: ``pending`` (M2) — a paid Razorpay subscription created, awaiting the first
#: confirmed charge; the webhook flips it to ``active``. ``past_due`` (M4) — a
#: renewal charge failed and Razorpay is retrying (dunning); a recovered charge
#: re-activates, exhausted retries expire.
_SUBSCRIPTION_STATUSES = ("pending", "active", "cancelled", "expired", "past_due")

#: Per-subscriber execution mode (M3 settings UI). ``paper`` is the default and
#: the ONLY mode that runs today — real-money subscriber execution is a later
#: phase (post-empanelment), so auto/one_click/offline are inert previews.
ExecutionMode = Literal["auto", "one_click", "offline", "paper"]
_EXECUTION_MODES: tuple[str, ...] = ("auto", "one_click", "offline", "paper")


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
    status: Literal["pending", "active", "cancelled", "expired", "past_due"]
    amount_paid_inr: float


class SubscriptionListResponse(BaseModel):
    subscriptions: list[SubscriptionRead]
    count: int


class MarketplaceSubscribeResponse(SubscriptionRead):
    """Subscribe result. Superset of :class:`SubscriptionRead` (so existing
    consumers keep reading ``id`` / ``status`` / ``amount_paid_inr``) plus the
    Razorpay checkout handle when payment is required.

    Two shapes:
      * Free listing OR gateway not configured → ``requires_payment=False``,
        the sub is already ``active`` (Phase-1 stub behaviour preserved), all
        ``razorpay_*`` fields ``None``.
      * Paid listing + Razorpay configured → ``requires_payment=True``, the sub
        is ``pending`` and the frontend opens checkout with
        ``razorpay_subscription_id`` + the PUBLIC ``razorpay_key_id``. The sub
        only becomes ``active`` once the verified webhook confirms the charge.
    """

    requires_payment: bool = False
    razorpay_subscription_id: str | None = None
    razorpay_key_id: str | None = None  # PUBLIC key id only — never the secret
    razorpay_short_url: str | None = None


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


class SubscriptionSettingsUpdate(BaseModel):
    """PATCH body — per-subscriber sizing + execution mode (M3).

    All fields optional (partial update). ``lots_override`` must be an EVEN
    integer, 2-20 (the platform's even-quantity rule, 4/6/8…). ``execution_mode``
    defaults to ``paper`` and is the only live mode today.
    """

    model_config = ConfigDict(extra="forbid")

    lots_override: int | None = Field(default=None, ge=2, le=20)
    execution_mode: ExecutionMode | None = None
    is_paper: bool | None = None

    @field_validator("lots_override")
    @classmethod
    def _even_lots(cls, v: int | None) -> int | None:
        if v is not None and v % 2 != 0:
            raise ValueError("lots_override must be an even number (minimum 2).")
        return v


class SubscriptionSettingsRead(BaseModel):
    """Per-subscriber settings + whether they are persisted on this branch.

    The execution-settings COLUMNS (lots_override / execution_mode / is_paper)
    land with the ``feat/marketplace-fanout`` (M4) merge. Until then this branch
    has no place to store them: ``applied`` is False and the values echo the
    request (validated but not persisted). The frontend renders them as a
    paper-only preview.
    """

    subscription_id: uuid.UUID
    lots_override: int | None
    execution_mode: ExecutionMode
    is_paper: bool
    applied: bool
    pending_fanout_merge: bool


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


def _public_key_id() -> str | None:
    """The PUBLIC Razorpay key id for the frontend checkout (never the secret)."""
    from app.core.config import get_settings

    key = get_settings().razorpay_key_id.get_secret_value()
    return key or None


def _sub_to_subscribe_response(
    sub: MarketplaceSubscription,
    *,
    requires_payment: bool = False,
    razorpay_subscription_id: str | None = None,
    razorpay_key_id: str | None = None,
    razorpay_short_url: str | None = None,
) -> MarketplaceSubscribeResponse:
    """Build the subscribe response from a sub row + optional checkout handle."""
    return MarketplaceSubscribeResponse(
        id=sub.id,
        listing_id=sub.listing_id,
        subscriber_id=sub.subscriber_id,
        subscribed_at=sub.subscribed_at,
        access_until=sub.access_until,
        status=sub.status,  # type: ignore[arg-type]
        amount_paid_inr=float(sub.amount_paid_inr),
        requires_payment=requires_payment,
        razorpay_subscription_id=razorpay_subscription_id,
        razorpay_key_id=razorpay_key_id,
        razorpay_short_url=razorpay_short_url,
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


#: Hard cap on rows returned by ``browse_listings``. Without this
#: a populated marketplace would load every published listing into
#: memory on every browse-page hit. A 100-row cap covers the
#: largest reasonable first-page render with room to spare; cursor
#: pagination is a Phase 2 item (PERFORMANCE_NOTES.md).
_BROWSE_MAX_ROWS = 100


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

    Result set is capped at ``_BROWSE_MAX_ROWS`` (100) to bound
    worst-case latency once the marketplace has thousands of rows;
    the composite index ``(status, published_at DESC)`` from
    Migration 022 makes this an index-only scan.
    """
    stmt = select(MarketplaceListing).where(
        MarketplaceListing.status == "published"
    )
    if max_price is not None:
        stmt = stmt.where(MarketplaceListing.price_inr <= Decimal(str(max_price)))
    if min_rating is not None:
        stmt = stmt.where(MarketplaceListing.rating_avg >= Decimal(str(min_rating)))
    stmt = stmt.order_by(MarketplaceListing.published_at.desc()).limit(
        _BROWSE_MAX_ROWS
    )

    rows = (await db.execute(stmt)).scalars().all()
    if tag is not None:
        # Tag filter happens in Python because ``tags`` is a JSON
        # column and JSONB containment isn't portable across our
        # SQLite test target. Phase 2 migrates to ``ARRAY(String)``
        # on Postgres + a GIN index so this filter pushes down.
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
    response_model=MarketplaceSubscribeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe_to_listing(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> MarketplaceSubscribeResponse:
    """Subscribe to a published listing.

    Phase 2 (Razorpay), Module 2 — two paths, decided by gateway config + price:

      * **Paid listing + Razorpay configured** → create a recurring Razorpay
        Subscription and persist a ``pending`` sub. The caller is NOT a paying
        subscriber until the verified webhook confirms the first charge (which
        flips the sub to ``active``). Returns the checkout handle.
      * **Free listing OR gateway not configured** → the Phase-1 stub path:
        record an ``active`` sub immediately with ``amount_paid_inr ==
        listing.price_inr`` (₹0 for free). No money moves.

    Either way this is access-only: a paid, active subscription does NOT enable
    real trading — fan-out stays disabled and execution stays PAPER until a
    later phase. Touches no trading code.
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

    # Already active OR pending? Idempotent re-call returns the existing row
    # rather than creating a duplicate Razorpay subscription / violating the
    # partial unique index.
    existing = (
        await db.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.listing_id == listing_id,
                MarketplaceSubscription.subscriber_id == current_user.id,
                MarketplaceSubscription.status.in_(("active", "pending")),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _sub_to_subscribe_response(
            existing,
            requires_payment=existing.status == "pending",
            razorpay_subscription_id=existing.razorpay_subscription_id,
            razorpay_key_id=(
                _public_key_id() if existing.status == "pending" else None
            ),
        )

    paid_via_gateway = float(listing.price_inr) > 0 and razorpay_configured()

    if paid_via_gateway:
        # ── Real recurring flow: pending until the webhook confirms charge ──
        try:
            result = await razorpay_billing.create_subscription_for_listing(
                db, user=current_user, listing=listing
            )
        except RazorpayConfigError as exc:  # defensive — gateway vanished mid-call
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payments are not configured.",
            ) from exc
        sub = result["marketplace_subscription"]
        logger.info(
            "marketplace.subscription.pending",
            listing_id=str(listing_id), subscriber_id=str(current_user.id),
            razorpay_subscription_id=result["razorpay_subscription_id"],
        )
        from app.observability import hash_resource_id, track_event

        track_event(
            user_id=str(current_user.id),
            event_name="marketplace_subscribe_initiated",
            properties={
                "listing_id_hash": hash_resource_id("listing", str(listing_id)),
                "amount_inr": result["amount_inr"],
            },
        )
        return _sub_to_subscribe_response(
            sub,
            requires_payment=True,
            razorpay_subscription_id=result["razorpay_subscription_id"],
            razorpay_key_id=result["razorpay_key_id"],
            razorpay_short_url=result["short_url"],
        )

    # ── Free / unconfigured path: immediate active (Phase-1 stub preserved) ──
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
    return _sub_to_subscribe_response(sub)


@router.delete(
    "/listings/{listing_id}/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unsubscribe_from_listing(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Cancel the caller's active subscription.

    FREE sub (no gateway): immediate cancel + release the seat → 204.
    PAID recurring sub: request Razorpay **cancel-at-period-end** — the seat +
    access are retained until the period ends, then the verified webhook flips
    the status. Returns 200 with ``{scheduled_cancel: true, access_until}``.
    The row stays in the table either way so ratings (which require
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

    # Paid recurring sub → cancel at the gateway (period-end); access retained.
    if sub.razorpay_subscription_id:
        from app.services.razorpay_client import RazorpayConfigError

        try:
            result = await razorpay_billing.cancel_marketplace_subscription(
                db, sub=sub, at_cycle_end=True
            )
        except RazorpayConfigError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payments are not configured.",
            ) from exc
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)

    # Free sub → immediate cancel + release the seat.
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


# ─── Per-subscriber settings (sizing + execution mode) ─────────────────
# The execution-settings columns (lots_override / execution_mode / is_paper)
# are added by the fan-out track (feat/marketplace-fanout, M4). On THIS branch
# they're absent, so writes are validated-but-not-persisted (``applied=False``)
# until that merge lands. The endpoint shape is the forward contract.


async def _load_owned_subscription(
    db: AsyncSession, subscription_id: uuid.UUID, user: User
) -> MarketplaceSubscription:
    sub = (
        await db.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.id == subscription_id,
                MarketplaceSubscription.subscriber_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found.",
        )
    return sub


def _columns_present(sub: MarketplaceSubscription) -> bool:
    """True once the fan-out execution-settings columns exist on the model."""
    return hasattr(sub, "execution_mode")


def _settings_response(
    sub: MarketplaceSubscription,
    *,
    lots_override: int | None,
    execution_mode: str,
    is_paper: bool,
    applied: bool,
) -> SubscriptionSettingsRead:
    return SubscriptionSettingsRead(
        subscription_id=sub.id,
        lots_override=lots_override,
        execution_mode=execution_mode,  # type: ignore[arg-type]
        is_paper=is_paper,
        applied=applied,
        pending_fanout_merge=not applied,
    )


@router.get(
    "/subscriptions/{subscription_id}/settings",
    response_model=SubscriptionSettingsRead,
)
async def get_subscription_settings(
    subscription_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SubscriptionSettingsRead:
    """Read the caller's per-subscriber settings. Defaults to paper-only when
    the fan-out columns aren't present on this branch yet."""
    sub = await _load_owned_subscription(db, subscription_id, current_user)
    present = _columns_present(sub)
    return _settings_response(
        sub,
        lots_override=getattr(sub, "lots_override", None),
        execution_mode=getattr(sub, "execution_mode", None) or "paper",
        is_paper=bool(getattr(sub, "is_paper", True)),
        applied=present,
    )


@router.patch(
    "/subscriptions/{subscription_id}/settings",
    response_model=SubscriptionSettingsRead,
)
async def update_subscription_settings(
    subscription_id: uuid.UUID,
    body: SubscriptionSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SubscriptionSettingsRead:
    """Update sizing + execution mode for one of the caller's subscriptions.

    Validates the even/2-20 sizing rule + the execution-mode enum regardless of
    branch. Persists ONLY when the fan-out columns exist (post-M4 merge); else
    echoes the validated values with ``applied=False`` (the UI shows a
    paper-only preview). Touches NO trading code.
    """
    sub = await _load_owned_subscription(db, subscription_id, current_user)
    present = _columns_present(sub)

    # Current values (defaults when columns absent).
    cur_lots = getattr(sub, "lots_override", None)
    cur_mode = getattr(sub, "execution_mode", None) or "paper"
    cur_paper = bool(getattr(sub, "is_paper", True))

    new_lots = body.lots_override if body.lots_override is not None else cur_lots
    new_mode = body.execution_mode if body.execution_mode is not None else cur_mode
    new_paper = body.is_paper if body.is_paper is not None else cur_paper

    if present:
        sub.lots_override = new_lots  # type: ignore[attr-defined]
        sub.execution_mode = new_mode  # type: ignore[attr-defined]
        sub.is_paper = new_paper  # type: ignore[attr-defined]
        await db.commit()
        logger.info(
            "marketplace.subscription.settings.updated",
            subscription_id=str(subscription_id),
            execution_mode=new_mode, lots_override=new_lots, is_paper=new_paper,
        )
    else:
        logger.info(
            "marketplace.subscription.settings.pending_fanout_merge",
            subscription_id=str(subscription_id),
        )

    return _settings_response(
        sub,
        lots_override=new_lots,
        execution_mode=new_mode,
        is_paper=new_paper,
        applied=present,
    )


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
