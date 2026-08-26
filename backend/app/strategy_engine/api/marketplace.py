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

Status (the Phase-1 deferral list below is largely shipped now):

    * Payment integration is BUILT (Razorpay: subscribe / cancel / change-plan /
      HMAC webhook) but DORMANT in prod — keys empty + ``PAYWALL_ENFORCED`` off.
      Free / gateway-unconfigured listings still record
      ``amount_paid_inr = listing.price_inr`` at subscribe time.
    * The Strategy Transparency Ledger snapshot is BUILT (was Phase 2).
    * The frontend is SHIPPED (was Phase 3).
    * "Royalty / payout" is SUPERSEDED — the platform is FLAT subscription
      (no profit / revenue share); marketplace price is a flat per-listing
      ``price_inr``, never a share of profit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone
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
from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_rating import MarketplaceRating
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_signal import StrategySignal
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


class SubscriptionDriftNotice(BaseModel):
    """Why this subscription was switched to MANUAL by the drift detector.

    Derived entirely from the append-only ``audit_logs`` table — no column and
    no migration. Present ONLY while the flip is still in effect: a later
    user-initiated mode change supersedes it (see ``_drift_notices_for_user``),
    so re-enabling AUTO clears the notice on its own.
    """

    flipped_at: datetime
    symbol: str | None
    #: ``broker_flat`` (closed entirely) | ``broker_partial`` (part-closed).
    reason: str


class SubscriptionOpenPosition(BaseModel):
    """The subscription's current open position, when it has one.

    Exists so a subscriber can PAUSE and then CLOSE from My Strategies. The
    owner-scoped ``/strategies/positions`` endpoint deliberately filters
    ``subscription_id IS NULL`` to keep subscriber rows out of the live-money
    path, and that filter is NOT relaxed — this is an additive, subscriber-side
    read instead.
    """

    id: uuid.UUID
    symbol: str
    #: RETAINED verbatim: this is ``remaining_quantity``, and the shipped Close
    #: button already reads it. ``remaining_quantity`` below is the same number
    #: under its real name — this alias stays so the existing UI keeps working.
    quantity: int

    # ── Position detail (Step 6, ADDITIVE + all optional) ──────────────
    # Prices are STRINGS, matching SubscriberSignalRead's entry/stop_loss/
    # target. A Decimal serialised as a JSON float silently re-rounds; these
    # are money, so they travel as the exact text the DB holds.
    side: str | None = None
    avg_entry_price: str | None = None
    remaining_quantity: int | None = None
    stop_loss_price: str | None = None
    target_price: str | None = None
    opened_at: datetime | None = None
    #: TRI-STATE, derived from the execution that OPENED this position — the
    #: same derivation the execution log uses, never a constant. The position
    #: card is the ALWAYS-VISIBLE surface (the log sits behind an expand), so
    #: if anything on this screen must not read as a live broker position, it
    #: is this. ``None`` => the row does not say; the UI claims neither.
    paper_mode: bool | None = None


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    subscriber_id: uuid.UUID
    subscribed_at: datetime
    access_until: datetime | None
    status: Literal["pending", "active", "cancelled", "expired", "past_due"]
    amount_paid_inr: float
    #: ADDITIVE + optional: set only when this subscription is currently
    #: flipped to MANUAL by broker drift. Existing consumers are unaffected.
    drift_notice: SubscriptionDriftNotice | None = None
    #: ADDITIVE + optional: the open position for THIS subscription, or None.
    #: None means the UI shows no Close control at all (never a disabled one).
    open_position: SubscriptionOpenPosition | None = None
    #: ADDITIVE: the EXISTING execution_mode column, simply surfaced. The UI
    #: needs it to render Pause vs Resume; 'offline' means paused (alerts only).
    #: Defaults to None for rows predating the fan-out columns.
    execution_mode: str | None = None
    #: ADDITIVE: the subscribed listing's title. Without it the UI had nothing
    #: to render but ``listing_id``, so the customer's own My Strategies page
    #: showed "Listing a1b2c3d4…" — a raw UUID stub — where the strategy name
    #: belongs. Joined the same way SubscriberSignalRead already joins it.
    #: Optional so a subscription whose listing row is gone still serialises.
    listing_title: str | None = None


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


#: audit_logs.action written by the drift detector on an AUTO->MANUAL flip.
_DRIFT_FLIP_ACTION = "marketplace.subscription.auto_to_manual.broker_drift"
#: audit_logs.action written HERE when the customer changes the mode themselves.
_MODE_USER_CHANGE_ACTION = "marketplace.subscription.execution_mode.user_change"
_AUDIT_RESOURCE_TYPE = "marketplace_subscription"


async def _drift_notices_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[str, SubscriptionDriftNotice]:
    """Latest live drift notice per subscription, for ONE user.

    ⚠️ USER-SCOPED BY CONSTRUCTION: the query filters ``AuditLog.user_id ==
    user_id`` (an indexed column), so a caller can only ever read their own
    rows. A customer must never see another customer's drift.

    Self-clearing: a notice is suppressed when the customer has changed the mode
    themselves SINCE the flip. That is why the settings endpoint records a
    user-change audit row — comparing the two timestamps is what makes
    re-enabling AUTO clear the banner without any stored "dismissed" flag.

    One grouped query over both action types (indexed on ``action``).
    """
    rows = (
        await db.execute(
            select(AuditLog)
            .where(
                AuditLog.user_id == user_id,
                AuditLog.action.in_(
                    (_DRIFT_FLIP_ACTION, _MODE_USER_CHANGE_ACTION)
                ),
                AuditLog.resource_type == _AUDIT_RESOURCE_TYPE,
            )
            .order_by(AuditLog.created_at.desc())
        )
    ).scalars().all()

    latest_flip: dict[str, AuditLog] = {}
    latest_user_change: dict[str, datetime] = {}
    for row in rows:  # newest first — first hit per key wins
        key = str(row.resource_id or "")
        if not key:
            continue
        if row.action == _DRIFT_FLIP_ACTION:
            latest_flip.setdefault(key, row)
        else:
            latest_user_change.setdefault(key, row.created_at)

    out: dict[str, SubscriptionDriftNotice] = {}
    for key, flip in latest_flip.items():
        changed_at = latest_user_change.get(key)
        if changed_at is not None and changed_at >= flip.created_at:
            continue  # customer has since set the mode themselves — cleared
        meta = flip.audit_metadata or {}
        out[key] = SubscriptionDriftNotice(
            flipped_at=flip.created_at,
            symbol=meta.get("symbol"),
            reason=str(meta.get("reason") or "broker_flat"),
        )
    return out


def _price_str(value: Decimal | None) -> str | None:
    """Money -> exact text. Never a float: a JSON float re-rounds silently."""
    return None if value is None else str(value)


#: Every key any writer has used to mark a simulated fill. They DISAGREE:
#: ``confirm_subscriber_signal`` writes ``paper_mode``; both fan-out writers
#: (entry and exit) write ``paper``. Reading only one of them would silently
#: report the other's rows as "not simulated" — a paper fill dressed up as a
#: broker fill. Any new writer must add its key HERE, and the test that pins
#: this tuple to the writers will fail until it does.
_PAPER_FLAG_KEYS: tuple[str, ...] = ("paper_mode", "paper")


def _execution_paper_mode(broker_response: Any) -> bool | None:
    """Derive the simulated/real flag from the row itself. Never hardcoded.

    Returns ``None`` when the row carries no usable flag — including when the
    value is present but not a bool (a truthy string like ``"false"`` must not
    silently read as True).
    """
    if not isinstance(broker_response, dict):
        return None
    for key in _PAPER_FLAG_KEYS:
        value = broker_response.get(key)
        if isinstance(value, bool):
            return value
    return None


async def _listing_titles_for_subscriptions(
    db: AsyncSession, listing_ids: list[uuid.UUID]
) -> dict[str, str]:
    """``listing_id -> title`` for the listings the caller subscribes to.

    Titles are PUBLIC marketplace copy (the browse page shows them to everyone),
    so there is no cross-customer leak here — but the ids passed in still come
    from a ``subscriber_id == current_user.id`` query, so the query stays
    narrow. One grouped query, no N+1.
    """
    if not listing_ids:
        return {}
    rows = (
        await db.execute(
            select(MarketplaceListing.id, MarketplaceListing.title).where(
                MarketplaceListing.id.in_(listing_ids)
            )
        )
    ).all()
    return {str(lid): title for lid, title in rows}


async def _open_positions_for_subscriptions(
    db: AsyncSession, subscription_ids: list[uuid.UUID]
) -> dict[str, SubscriptionOpenPosition]:
    """Open/partial position per subscription, for the caller's OWN subs only.

    ⚠️ SCOPING: the ids passed in come from a query already filtered by
    ``subscriber_id == current_user.id``, and the WHERE below is restricted to
    exactly those ids — so a caller can never read another customer's position.
    A test holds this the same way the drift-notice scoping test does.

    One query for every subscription (no N+1).
    """
    if not subscription_ids:
        return {}
    from app.db.models.strategy_position import StrategyPosition

    rows = (
        await db.execute(
            select(StrategyPosition)
            .where(
                StrategyPosition.subscription_id.in_(subscription_ids),
                StrategyPosition.status.in_(("open", "partial")),
            )
            .order_by(StrategyPosition.opened_at.desc())
        )
    ).scalars().all()

    # The simulated/real flag for each position, derived from the execution
    # that OPENED it (same signal + same subscription). ONE grouped query, not
    # one per position. A position with no locatable opening execution stays
    # None — unknown, never guessed.
    paper_by_position: dict[uuid.UUID, bool | None] = {}
    signal_ids = [r.signal_id for r in rows if r.signal_id is not None]
    if signal_ids:
        exec_rows = (
            await db.execute(
                select(
                    StrategyExecution.signal_id,
                    StrategyExecution.subscription_id,
                    StrategyExecution.broker_response,
                ).where(
                    StrategyExecution.signal_id.in_(signal_ids),
                    StrategyExecution.subscription_id.in_(subscription_ids),
                )
            )
        ).all()
        by_key = {
            (sig, sub): resp for sig, sub, resp in exec_rows
        }
        for r in rows:
            if r.signal_id is None:
                continue
            key = (r.signal_id, r.subscription_id)
            if key in by_key:
                paper_by_position[r.id] = _execution_paper_mode(by_key[key])

    out: dict[str, SubscriptionOpenPosition] = {}
    for row in rows:  # newest first — first hit per subscription wins
        key = str(row.subscription_id)
        out.setdefault(
            key,
            SubscriptionOpenPosition(
                id=row.id,
                symbol=row.symbol,
                quantity=int(row.remaining_quantity or 0),
                side=row.side,
                avg_entry_price=_price_str(row.avg_entry_price),
                remaining_quantity=int(row.remaining_quantity or 0),
                stop_loss_price=_price_str(row.stop_loss_price),
                target_price=_price_str(row.target_price),
                opened_at=row.opened_at,
                paper_mode=paper_by_position.get(row.id),
            ),
        )
    return out


def _sub_to_read(
    sub: MarketplaceSubscription,
    drift_notice: SubscriptionDriftNotice | None = None,
    open_position: SubscriptionOpenPosition | None = None,
    listing_title: str | None = None,
) -> SubscriptionRead:
    return SubscriptionRead(
        drift_notice=drift_notice,
        open_position=open_position,
        listing_title=listing_title,
        execution_mode=getattr(sub, "execution_mode", None),
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
    # ONE grouped audit query for the caller's OWN drift notices.
    notices = await _drift_notices_for_user(db, current_user.id)
    # Scoped to the caller's OWN subscription ids (rows is already filtered by
    # subscriber_id), so this can never surface another customer's position.
    positions = await _open_positions_for_subscriptions(db, [r.id for r in rows])
    titles = await _listing_titles_for_subscriptions(db, [r.listing_id for r in rows])
    items = [
        _sub_to_read(
            r,
            notices.get(str(r.id)),
            positions.get(str(r.id)),
            titles.get(str(r.listing_id)),
        )
        for r in rows
    ]
    return SubscriptionListResponse(subscriptions=items, count=len(items))


# ─── Subscriber signal feed ────────────────────────────────────────────
# A subscriber sees the signals of the strategies they ACTIVELY subscribe to.
# Read-only + BLACK-BOX: signal-level fields (symbol / action / entry, plus
# SL/target ONLY if the alert carried them) + a SERVER-computed validity window,
# but NEVER strategy internals — no strategy_json / indicators / Pine, and SL &
# target are read from the raw payload only, never derived from the strategy's
# SL%/target% config (that would leak the edge). Places no order, no broker call.


class SignalValidity(BaseModel):
    """Server-computed validity — the frontend countdown is backed by this, not
    a client clock. ENTRY: 5-minute window from ``received_at``. Exit
    (EXIT/PARTIAL/SL_HIT): valid until 15:30 IST (EOD) on the received day."""

    window: Literal["entry", "exit"]
    valid: bool
    expires_at: datetime
    seconds_remaining: int


class SubscriberSignalRead(BaseModel):
    """One signal from a subscribed strategy — masked to signal-level fields."""

    id: uuid.UUID
    listing_id: uuid.UUID
    listing_title: str
    symbol: str
    action: str
    side: str | None
    entry: str | None
    stop_loss: str | None
    target: str | None
    received_at: datetime
    status: str
    validity: SignalValidity


class SubscriberSignalListResponse(BaseModel):
    signals: list[SubscriberSignalRead]
    count: int


#: IST = UTC + 5:30; exit signals are valid until the 15:30 IST EOD cutoff.
_IST_TZ = timezone(timedelta(hours=5, minutes=30))
_ENTRY_VALIDITY = timedelta(minutes=5)


def _payload_field(payload: dict[str, Any], *keys: str) -> str | None:
    """First present, non-empty value among ``keys`` in the raw payload, as a
    string. Payload-only — NEVER reads strategy config."""
    for k in keys:
        v = payload.get(k)
        if v is not None and str(v).strip() != "":
            return str(v)
    return None


def _compute_signal_validity(
    action: str, received_at: datetime, now_utc: datetime
) -> SignalValidity:
    r = received_at if received_at.tzinfo else received_at.replace(tzinfo=UTC)
    if "ENTRY" in (action or "").upper():
        window: Literal["entry", "exit"] = "entry"
        expires_at = r + _ENTRY_VALIDITY
    else:
        window = "exit"
        r_ist = r.astimezone(_IST_TZ)
        eod_ist = r_ist.replace(hour=15, minute=30, second=0, microsecond=0)
        expires_at = eod_ist.astimezone(UTC)
    seconds_remaining = max(0, int((expires_at - now_utc).total_seconds()))
    return SignalValidity(
        window=window,
        valid=now_utc < expires_at,
        expires_at=expires_at,
        seconds_remaining=seconds_remaining,
    )


def _to_subscriber_signal(
    signal: StrategySignal,
    listing: tuple[uuid.UUID, str],
    now_utc: datetime,
) -> SubscriberSignalRead:
    listing_id, listing_title = listing
    payload = signal.raw_payload or {}
    return SubscriberSignalRead(
        id=signal.id,
        listing_id=listing_id,
        listing_title=listing_title,
        symbol=signal.symbol,
        action=signal.action,
        side=_payload_field(payload, "side"),
        entry=_payload_field(payload, "price", "entry"),
        # SL/target ONLY when the alert explicitly carried them — never the
        # strategy's config-derived SL%/target% (those are internals).
        stop_loss=_payload_field(payload, "sl", "stop", "stop_loss", "stopLoss"),
        target=_payload_field(payload, "target", "tp", "takeProfit"),
        received_at=signal.received_at,
        status=signal.status,
        validity=_compute_signal_validity(
            signal.action, signal.received_at, now_utc
        ),
    )


@router.get("/subscriptions/signals", response_model=SubscriberSignalListResponse)
async def list_subscriber_signals(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=500),
    status_filter: str | None = Query(default=None, alias="status"),
) -> SubscriberSignalListResponse:
    """Signals from the strategies the caller ACTIVELY subscribes to, newest
    first.

    Distinct from ``GET /api/strategies/signals`` (owner-scoped — a user's OWN
    strategies). This is the SUBSCRIBER view: active subscriptions → their
    listings → those listings' strategies → those strategies' signals. Only
    ``status='active'`` subscriptions count (cancelled/expired see nothing).
    Read-only + black-box; places no order, touches no broker.
    """
    # 1. Active subscriptions → subscribed strategies (+ the public listing).
    sub_rows = (
        await db.execute(
            select(
                MarketplaceListing.strategy_id,
                MarketplaceListing.id,
                MarketplaceListing.title,
            )
            .join(
                MarketplaceSubscription,
                MarketplaceSubscription.listing_id == MarketplaceListing.id,
            )
            .where(
                MarketplaceSubscription.subscriber_id == current_user.id,
                MarketplaceSubscription.status == "active",
            )
        )
    ).all()
    if not sub_rows:
        return SubscriberSignalListResponse(signals=[], count=0)

    strat_to_listing: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    for strategy_id, listing_id, title in sub_rows:
        strat_to_listing.setdefault(strategy_id, (listing_id, title))

    # 2. Recent signals for those strategies. Filtered by strategy_id (NOT
    #    user_id) — that is exactly what lets a subscriber see the OWNER's
    #    signals for a strategy they subscribe to.
    sig_stmt = (
        select(StrategySignal)
        .where(StrategySignal.strategy_id.in_(list(strat_to_listing.keys())))
        .order_by(StrategySignal.received_at.desc())
        .limit(limit)
    )
    if status_filter:
        sig_stmt = sig_stmt.where(StrategySignal.status == status_filter)
    signals = (await db.execute(sig_stmt)).scalars().all()

    now_utc = datetime.now(UTC)
    items = [
        _to_subscriber_signal(s, strat_to_listing[s.strategy_id], now_utc)
        for s in signals
    ]
    return SubscriberSignalListResponse(signals=items, count=len(items))


# ─── Confirm / take-trade (LIVE-MONEY-CRITICAL — PAPER-GATED) ───────────
# A subscriber confirms ONE signal from a strategy they ACTIVELY subscribe to,
# and a PAPER (simulated) fill is recorded for their subscription. Kill-switch-
# class rigor:
#   * scoped to ONE signal_id + the caller's OWN active subscription;
#   * server-side validity RE-CHECK (never trust a client countdown);
#   * IDEMPOTENT — a second confirm of the same (signal, subscription) returns
#     the existing execution, never a second fill;
#   * PAPER ONLY — the sole fill primitive is ``_simulate_fill`` (no broker,
#     ever). This endpoint contains NO real-broker path. Real placement is a
#     SEPARATE, gated task that must route through the existing execution path
#     under an explicit per-subscription ``is_paper=false`` AND the fan-out flag;
#     until then a real-eligible confirm still records PAPER and says so.


class ConfirmSignalResult(BaseModel):
    signal_id: uuid.UUID
    subscription_id: uuid.UUID
    #: ``confirmed_paper`` (fresh paper fill) | ``already_confirmed`` (idempotent).
    status: Literal["confirmed_paper", "already_confirmed"]
    #: ALWAYS False in this build — no real order is ever placed here.
    placed_real: bool
    execution_id: uuid.UUID
    broker_order_id: str | None
    quantity: int
    price: str | None
    validity: SignalValidity
    note: str


def _confirm_side(action: str, payload: dict[str, Any]) -> str:
    """Best-effort buy/sell for the paper execution record (paper — not
    money-moving). Payload ``side`` wins; else derived from the action."""
    raw = _payload_field(payload, "side")
    if raw and raw.lower() in ("buy", "sell"):
        return raw.lower()
    up = (action or "").upper()
    if raw and raw.lower() in ("long", "short"):
        return "buy" if raw.lower() == "long" else "sell"
    if "SHORT" in up:
        return "sell"
    if any(k in up for k in ("EXIT", "SL", "PARTIAL")):
        return "sell"
    return "buy"


@router.post(
    "/subscriptions/signals/{signal_id}/confirm",
    response_model=ConfirmSignalResult,
)
async def confirm_subscriber_signal(
    signal_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ConfirmSignalResult:
    """Confirm ONE signal → record a PAPER fill for the caller's active
    subscription. Paper-gated, idempotent, server-validity-checked, no broker.
    """
    from app.core.config import get_settings
    from app.services.strategy_executor import _simulate_fill

    # 1. The signal must exist.
    signal = await db.get(StrategySignal, signal_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found."
        )

    # 2. The caller must ACTIVELY subscribe to that signal's strategy — the SAME
    #    active-subscription scoping as the feed. 404 (not 403) so a non-
    #    subscriber can't even confirm the signal's existence.
    sub = (
        await db.execute(
            select(MarketplaceSubscription)
            .join(
                MarketplaceListing,
                MarketplaceListing.id == MarketplaceSubscription.listing_id,
            )
            .where(
                MarketplaceListing.strategy_id == signal.strategy_id,
                MarketplaceSubscription.subscriber_id == current_user.id,
                MarketplaceSubscription.status == "active",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription for this signal's strategy.",
        )

    # 3. SERVER-SIDE validity re-check — a lapsed signal cannot be confirmed.
    now_utc = datetime.now(UTC)
    validity = _compute_signal_validity(signal.action, signal.received_at, now_utc)
    if not validity.valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Signal validity lapsed ({validity.window} window closed). "
                "Cannot confirm."
            ),
        )

    # 4. IDEMPOTENT — a prior confirm for THIS (signal, subscription) wins; never
    #    a second fill. (Durable on retry; a unique constraint would additionally
    #    close the concurrent-double-submit window for the real-money phase.)
    existing = (
        await db.execute(
            select(StrategyExecution)
            .where(
                StrategyExecution.signal_id == signal_id,
                StrategyExecution.subscription_id == sub.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ConfirmSignalResult(
            signal_id=signal_id, subscription_id=sub.id,
            status="already_confirmed", placed_real=False,
            execution_id=existing.id, broker_order_id=existing.broker_order_id,
            quantity=int(existing.quantity),
            price=str(existing.price) if existing.price is not None else None,
            validity=validity,
            note="Idempotent — this signal was already confirmed for this subscription.",
        )

    # 5. PAPER-GATE. This endpoint NEVER places a real order. real_eligible is
    #    computed only to be honest in the response — the real path is a
    #    separate, gated task (is_paper=false AND the fan-out flag).
    real_eligible = (sub.is_paper is False) and bool(
        get_settings().marketplace_fanout_enabled
    )

    # 6. A NOT-NULL broker-credential anchor for the paper record (never used to
    #    build/call a broker). Prefer the subscriber's own; else the strategy's
    #    (the owner's placeholder, as the fan-out uses).
    cred_id = sub.broker_credential_id
    if cred_id is None:
        cred_id = (
            await db.execute(
                select(Strategy.broker_credential_id).where(
                    Strategy.id == signal.strategy_id
                )
            )
        ).scalar_one_or_none()
    if cred_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No broker credential available to anchor the paper record.",
        )

    # 7. PAPER fill — the ONLY execution primitive, pure, no broker.
    payload = signal.raw_payload or {}
    qty = int(sub.lots_override or signal.quantity or 1)
    sim = _simulate_fill(signal, qty)
    is_entry = "ENTRY" in (signal.action or "").upper()

    execution = StrategyExecution(
        signal_id=signal.id,
        broker_credential_id=cred_id,
        subscription_id=sub.id,
        leg_number=1,
        leg_role="entry" if is_entry else "exit",
        symbol=signal.symbol,
        side=_confirm_side(signal.action, payload),
        quantity=qty,
        order_type="market",
        price=sim.get("avg_price"),
        broker_order_id=sim.get("broker_order_id"),
        broker_status="complete",
        broker_response={
            "paper_mode": True,
            "source": "subscriber_confirm",
            "marketplace_subscription_id": str(sub.id),
            "real_eligible": real_eligible,
        },
        placed_at=now_utc,
        completed_at=now_utc,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    logger.info(
        "marketplace.subscriber_signal_confirmed",
        signal_id=str(signal_id),
        subscription_id=str(sub.id),
        subscriber_id=str(current_user.id),
        quantity=qty,
        real_eligible=real_eligible,
        placed_real=False,
    )
    note = (
        "PAPER confirmation. Real placement is NOT wired here — it will route "
        "through the existing execution path under is_paper=false + the fan-out "
        "flag (separate gated task)."
        if real_eligible
        else "PAPER confirmation (paper-gated; no real order placed)."
    )
    price = sim.get("avg_price")
    return ConfirmSignalResult(
        signal_id=signal_id, subscription_id=sub.id,
        status="confirmed_paper", placed_real=False,
        execution_id=execution.id, broker_order_id=execution.broker_order_id,
        quantity=qty, price=str(price) if price is not None else None,
        validity=validity, note=note,
    )


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
        if new_mode != cur_mode:
            # Record the CUSTOMER's own mode change. This is what lets a drift
            # notice self-clear: the banner is suppressed once a user-initiated
            # change is newer than the flip. Without this row we could keep
            # telling a customer "we switched you to manual because you closed
            # at your broker" after they had deliberately chosen manual
            # themselves — a false statement.
            db.add(
                AuditLog(
                    user_id=current_user.id,
                    actor=ActorType.USER,
                    action=_MODE_USER_CHANGE_ACTION,
                    resource_type=_AUDIT_RESOURCE_TYPE,
                    resource_id=str(subscription_id),
                    audit_metadata={"from": cur_mode, "to": new_mode},
                )
            )
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


# ═══════════════════════════════════════════════════════════════════════
# EMERGENCY EXIT — close a position from tradetri.com
# ═══════════════════════════════════════════════════════════════════════
# The counterpart to the AUTO->MANUAL drift flip: instead of the customer
# going to their broker, they exit here. Closing sets the position to
# ``closed``, which the fan-out's ``status.in_(("open","partial"))`` lookup no
# longer matches — so a later PARTIAL / EXIT / SL_HIT signal becomes a no-op
# (``skipped_no_position``) instead of firing an order. No new "done" flag.
#
# ⚠️ This is the FIRST endpoint in the subscriber stack that ACTS rather than
# withholding action, hence its OWN flag (``emergency_exit_enabled``, default
# False) so it is never coupled to the fan-out's blast radius. The actual close
# is delegated to the existing, tested ``KillSwitchService.kill_subscriber``
# (imported, never edited), which self-gates to a PAPER close for a paper
# subscription and never touches the owner's rows.

#: Idempotency slot TTL for a close. Long enough to cover a double-click and a
#: retry, short enough that a genuine second exit later is not blocked.
_EMERGENCY_EXIT_IDEMPOTENCY_TTL_SECONDS = 120


class ClosePositionRequest(BaseModel):
    """The position the customer believes they are closing.

    Required, and verified to belong to this subscription — so a stale UI can
    never close something other than what the customer clicked.
    """

    position_id: uuid.UUID


class ClosedPositionOutcome(BaseModel):
    position_id: uuid.UUID
    symbol: str | None
    #: ``closed`` | ``not_closed``. Never invented — derived from the row.
    outcome: str
    quantity_closed: int


class ClosePositionResult(BaseModel):
    subscription_id: uuid.UUID
    #: ``closed`` (all requested work done) | ``already_flat`` |
    #: ``partial`` (SOME did not close — NOT a success) | ``failed`` |
    #: ``dormant`` (flag off).
    status: str
    #: True only for a real broker close. False for paper — the UI must derive
    #: its wording from THIS, never hardcode it.
    placed_real: bool
    positions: list[ClosedPositionOutcome]
    #: Per-position broker errors, verbatim. Empty on a clean close.
    errors: list[str]
    note: str


@router.post(
    "/subscriptions/{subscription_id}/close-position",
    response_model=ClosePositionResult,
)
async def close_subscription_position(
    subscription_id: uuid.UUID,
    body: ClosePositionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ClosePositionResult:
    """Close this subscription's open position from tradetri.com.

    Ownership is asserted twice — the subscription must belong to the caller AND
    the position must belong to that subscription — so customer A can never
    close customer B's position.
    """
    from app.core import redis_client
    from app.core.config import get_settings
    from app.db.models.strategy_position import StrategyPosition

    if not get_settings().emergency_exit_enabled:
        return ClosePositionResult(
            subscription_id=subscription_id, status="dormant",
            placed_real=False, positions=[], errors=[],
            note="Emergency exit is not enabled.",
        )

    # 1. OWNERSHIP — the subscription must be the caller's. 404 (not 403) so a
    #    stranger cannot even confirm it exists.
    sub = (
        await db.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.id == subscription_id,
                MarketplaceSubscription.subscriber_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
        )

    # 2. OWNERSHIP, again — the position must belong to THIS subscription.
    position = (
        await db.execute(
            select(StrategyPosition).where(
                StrategyPosition.id == body.position_id,
                StrategyPosition.subscription_id == subscription_id,
            )
        )
    ).scalar_one_or_none()
    if position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found for this subscription.",
        )

    if str(position.status) not in ("open", "partial"):
        return ClosePositionResult(
            subscription_id=subscription_id, status="already_flat",
            placed_real=False,
            positions=[ClosedPositionOutcome(
                position_id=position.id, symbol=position.symbol,
                outcome="closed", quantity_closed=0)],
            errors=[],
            note="This position is already closed — nothing to do.",
        )

    # 3. IDEMPOTENCY — a read-then-act check on `status` cannot survive two
    #    concurrent clicks; only this claim closes that window.
    #    ⚠️ FAIL CLOSED, deliberately diverging from the fan-out's fail-open:
    #    a duplicate CLOSE on a live account could send a second order against a
    #    flat position and open an unwanted SHORT. Refusing is safe because the
    #    customer always retains their broker as a fallback exit.
    idem_key = f"emergency_exit:{subscription_id}:{body.position_id}"
    try:
        first = await redis_client.set_idempotency_key(
            idem_key, ttl_seconds=_EMERGENCY_EXIT_IDEMPOTENCY_TTL_SECONDS
        )
    except Exception as exc:
        logger.warning(
            "marketplace.emergency_exit.idempotency_unavailable",
            subscription_id=str(subscription_id), error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Could not safely de-duplicate this request. Nothing was "
                "closed — please retry, or close at your broker."
            ),
        ) from exc
    if not first:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A close for this position is already in progress.",
        )

    # 4. Delegate to the EXISTING tested primitive (imported, never edited).
    #    It self-gates: paper subscription -> paper close, no broker.
    from app.services.kill_switch_service import KillSwitchService

    result = await KillSwitchService().kill_subscriber(db, subscription_id)
    raw_status = str(result.get("status") or "failed")
    errors = [str(e) for e in (result.get("errors") or [])]

    # 5. Report from the ROW, never from the request. A position that did not
    #    close stays `open` — we must never mark done what was not closed, or a
    #    later exit signal would be silently disarmed on a still-live position.
    await db.refresh(position)
    closed = str(position.status) == "closed"
    outcome = ClosedPositionOutcome(
        position_id=position.id,
        symbol=position.symbol,
        outcome="closed" if closed else "not_closed",
        quantity_closed=int(result.get("closed") or 0) if closed else 0,
    )

    # NEVER report success on a partial.
    if raw_status == "dormant":
        final, note = "dormant", "Subscriber execution is not enabled."
    elif not closed or raw_status in ("partial", "failed"):
        final = "partial" if closed or raw_status == "partial" else "failed"
        note = (
            "Not everything could be closed. Please check your broker — any "
            "position still shown there is still live."
        )
    else:
        final = "closed"
        note = (
            "Position closed. Further signals for this trade will not place "
            "any order."
        )

    placed_real = bool(closed and sub.is_paper is False)
    if closed and sub.is_paper:
        note = f"PAPER close — no real broker order was placed. {note}"

    logger.info(
        "marketplace.emergency_exit",
        subscription_id=str(subscription_id),
        position_id=str(body.position_id),
        subscriber_id=str(current_user.id),
        status=final, placed_real=placed_real, errors=len(errors),
    )
    return ClosePositionResult(
        subscription_id=subscription_id, status=final,
        placed_real=placed_real, positions=[outcome], errors=errors, note=note,
    )


# ─── Subscriber execution log (Step 6) ──────────────────────────────────
# What ACTUALLY got placed for ONE of the caller's subscriptions.
#
# ⚠️ WHY THIS IS A SEPARATE ENDPOINT, and not a filter relaxed on
# ``GET /api/strategies/executions``:
#
#   That endpoint is OWNER-scoped through the signal —
#   ``StrategySignal.user_id == current_user.id`` AND
#   ``StrategyExecution.subscription_id IS NULL``. A subscriber's execution
#   hangs off the STRATEGY OWNER's signal, so ``signal.user_id`` is never the
#   subscriber's id. Dropping the NULL filter would therefore still return
#   nothing for a subscriber — while simultaneously exposing subscriber rows to
#   the owner. There is no filter tweak that makes it subscriber-safe. We go
#   AROUND that endpoint, never through it, exactly as the position read does.
#
# Read-only: no INSERT/UPDATE/DELETE, no broker call, no flag gate (the rows
# are written by the LIVE manual-confirm path, so this reads real data today).
#
# ⚠️ WHAT THIS LOG DOES NOT CONTAIN. ``KillSwitchService.kill_subscriber`` —
# the primitive behind the customer-facing Close button — writes NO
# ``StrategyExecution`` row (verified: zero references in
# app/services/kill_switch_service.py). So a position closed by hand shows its
# ENTRY here and no exit. That file is on the protected kill-switch path and is
# NOT edited to fix this; instead the UI SAYS the gap exists, because a log
# that quietly omits an exit reads as a position still running.


class SubscriptionExecutionRead(BaseModel):
    """One recorded order for this subscription.

    ``paper_mode`` is TRI-STATE and derived per row — never assumed:
      * ``True``  → simulated fill (everything written today)
      * ``False`` → a real broker fill
      * ``None``  → the row does not say

    ``None`` is NOT collapsed into either answer. Defaulting unknown→real would
    let a simulated fill be presented as a broker fill, which is the one thing
    this screen must never do; defaulting unknown→simulated would hard-code the
    very reassurance the label exists to earn. So the UI renders a third,
    non-claiming state instead. Same discipline as POSITION_UNKNOWN in the
    fan-out: absence of evidence is never evidence of absence.
    """

    id: uuid.UUID
    symbol: str
    side: str
    quantity: int
    leg_role: str
    order_type: str
    price: str | None
    broker_order_id: str | None
    broker_status: str | None
    error_code: str | None
    error_message: str | None
    placed_at: datetime
    completed_at: datetime | None
    paper_mode: bool | None


class SubscriptionExecutionListResponse(BaseModel):
    subscription_id: uuid.UUID
    executions: list[SubscriptionExecutionRead]
    #: How many rows are IN THIS RESPONSE — not how many exist.
    count: int
    #: True when the log was cut short by ``limit``. Without this, ``count``
    #: reads as a total and a customer with more history than the page size is
    #: quietly shown a partial log as if it were the whole one. A silent cap on
    #: a money screen is the same class of untruth as an invented number.
    truncated: bool = False


@router.get(
    "/subscriptions/{subscription_id}/executions",
    response_model=SubscriptionExecutionListResponse,
)
async def list_subscription_executions(
    subscription_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, ge=1, le=500),
) -> SubscriptionExecutionListResponse:
    """This subscription's execution log — newest first.

    Ownership is asserted TWICE, the same way ``close_subscription_position``
    does it: the subscription must belong to the caller, and the executions are
    then filtered to that subscription id. Customer A can never read customer
    B's executions.
    """
    # 1. OWNERSHIP — the subscription must be the caller's. 404 (not 403) so a
    #    stranger cannot even confirm the subscription exists.
    sub = (
        await db.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.id == subscription_id,
                MarketplaceSubscription.subscriber_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
        )

    # 2. SCOPED READ — filtered to THAT subscription id, which step 1 just
    #    proved belongs to the caller. Note this deliberately does NOT join
    #    through StrategySignal.user_id: that column holds the strategy OWNER's
    #    id, not the subscriber's, and joining on it would return nothing.
    # limit + 1: if the extra row comes back there IS more history than we are
    # showing, and the response says so instead of implying completeness.
    rows = (
        await db.execute(
            select(StrategyExecution)
            .where(StrategyExecution.subscription_id == subscription_id)
            .order_by(StrategyExecution.placed_at.desc())
            .limit(limit + 1)
        )
    ).scalars().all()
    truncated = len(rows) > limit
    rows = rows[:limit]

    items = [
        SubscriptionExecutionRead(
            id=r.id,
            symbol=r.symbol,
            side=r.side,
            quantity=int(r.quantity or 0),
            leg_role=r.leg_role,
            order_type=r.order_type,
            price=_price_str(r.price),
            broker_order_id=r.broker_order_id,
            broker_status=r.broker_status,
            error_code=r.error_code,
            error_message=r.error_message,
            placed_at=r.placed_at,
            completed_at=r.completed_at,
            paper_mode=_execution_paper_mode(r.broker_response),
        )
        for r in rows
    ]
    return SubscriptionExecutionListResponse(
        subscription_id=subscription_id, executions=items, count=len(items),
        truncated=truncated,
    )


# Defensive — silence unused-import warnings if a refactor strips them.
_ = ValidationError


__all__ = ["router"]
