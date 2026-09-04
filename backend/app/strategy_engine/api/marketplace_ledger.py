"""Marketplace Ledger API — Phase 2.

Five endpoints under ``/api/marketplace/listings/{listing_id}/ledger``:

    GET    /                         — latest snapshot
    GET    /history                  — paginated history (newest first)
    GET    /verify                   — chain integrity check
    GET    /snapshot/{seq}           — specific snapshot by sequence
    POST   /snapshot/now             — manual snapshot trigger
                                       (creator-only, 1 / day rate limit)

The manual trigger exists because Phase 2 ships without a
production cron — the frontend (Phase 3) and admin tooling can hit
the trigger to advance the chain. Phase 4's deferred work will
swap the manual trigger for a scheduled job + real Polygon
emission; the read APIs stay the same.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.auth.entitlements import require_active_plan
from app.auth.roles import require_creator_or_above
from app.core.logging import get_logger
from app.db.models.ledger_snapshot import LedgerSnapshot
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.ledger import (
    LedgerVerificationResult,
    create_daily_snapshot,
    verify_listing_chain,
)
from app.strategy_engine.ledger.snapshots import (
    ListingNotFoundError,
    NothingToPublishError,
    SnapshotAlreadyExistsError,
    SnapshotPayload,
    build_snapshot_preview,
)

logger = get_logger("app.strategy_engine.api.marketplace_ledger")

router = APIRouter(
    prefix="/api/marketplace/listings/{listing_id}/ledger",
    tags=["marketplace-ledger"],
)


# ─── Wire models ───────────────────────────────────────────────────────


class LedgerSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    snapshot_date: date
    sequence_number: int
    cumulative_pnl_inr: float
    #: % of the cumulative-P&L peak — paper listings; None for live listings.
    max_drawdown_pct: float | None
    #: Peak-to-trough drawdown of the cumulative NET series, in rupees (045).
    max_drawdown_inr: float | None = None
    total_trades: int
    win_rate: float
    sharpe_ratio: float | None
    days_since_publish: int
    paper_trades_count: int
    live_trades_count: int
    #: Closed positions the platform could not price (live listings).
    unpriced_positions: int | None = None
    #: Of those, positions tagged "human-interfered — not attributable": the
    #: founder's manual fills on the same contract made the exit a guess, so
    #: the P&L is NULL by rule, not missing by accident (046).
    human_interfered_positions: int | None = None
    #: ``reconciled_net_estimated_costs`` — NET of MODELLED charges — or
    #: ``paper_sessions_gross``. Fills are real; charges are our estimate,
    #: not the broker's contract note.
    pnl_basis: str | None = None
    data_hash: str
    prior_hash: str | None
    chain_signature: str
    created_at: datetime


class LedgerHistoryResponse(BaseModel):
    snapshots: list[LedgerSnapshotRead]
    count: int


# ─── Helpers ───────────────────────────────────────────────────────────


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)  # type: ignore[call-overload]


def _to_read(row: LedgerSnapshot) -> LedgerSnapshotRead:
    return LedgerSnapshotRead(
        id=row.id,
        listing_id=row.listing_id,
        snapshot_date=row.snapshot_date,
        sequence_number=int(row.sequence_number),
        cumulative_pnl_inr=float(row.cumulative_pnl_inr),
        max_drawdown_pct=(None if row.max_drawdown_pct is None else float(row.max_drawdown_pct)),
        max_drawdown_inr=(None if row.max_drawdown_inr is None else float(row.max_drawdown_inr)),
        total_trades=int(row.total_trades),
        win_rate=float(row.win_rate),
        sharpe_ratio=(float(row.sharpe_ratio) if row.sharpe_ratio is not None else None),
        days_since_publish=int(row.days_since_publish),
        paper_trades_count=int(row.paper_trades_count),
        live_trades_count=int(row.live_trades_count),
        unpriced_positions=(
            None if row.unpriced_positions is None else int(row.unpriced_positions)
        ),
        human_interfered_positions=_optional_int(getattr(row, "human_interfered_positions", None)),
        pnl_basis=row.pnl_basis,
        data_hash=row.data_hash,
        prior_hash=row.prior_hash,
        chain_signature=row.chain_signature,
        created_at=row.created_at,
    )


async def _ensure_listing_visible(
    db: AsyncSession, listing_id: uuid.UUID, user: User
) -> MarketplaceListing:
    """Fetch the listing or raise 404. Drafts owned by someone else
    are hidden — same visibility rule as ``GET /listings/{id}``."""
    listing = (
        await db.execute(select(MarketplaceListing).where(MarketplaceListing.id == listing_id))
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )
    if listing.status == "draft" and listing.creator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )
    return listing


# ─── Endpoints — read paths (any authenticated) ───────────────────────


@router.get("", response_model=LedgerSnapshotRead | None)
async def get_latest_snapshot(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> LedgerSnapshotRead | None:
    """Most recent snapshot for the listing, or ``null`` if no
    snapshot has been taken yet."""
    await _ensure_listing_visible(db, listing_id, current_user)
    row = (
        await db.execute(
            select(LedgerSnapshot)
            .where(LedgerSnapshot.listing_id == listing_id)
            .order_by(LedgerSnapshot.sequence_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _to_read(row) if row is not None else None


@router.get("/history", response_model=LedgerHistoryResponse)
async def get_snapshot_history(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LedgerHistoryResponse:
    """Paginated snapshot history, newest first."""
    await _ensure_listing_visible(db, listing_id, current_user)
    rows = (
        (
            await db.execute(
                select(LedgerSnapshot)
                .where(LedgerSnapshot.listing_id == listing_id)
                .order_by(LedgerSnapshot.sequence_number.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    items = [_to_read(r) for r in rows]
    return LedgerHistoryResponse(snapshots=items, count=len(items))


@router.get("/verify", response_model=LedgerVerificationResult)
async def verify_chain(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> LedgerVerificationResult:
    """Walk the chain end-to-end and report the first
    inconsistency (or ``is_chain_valid=True`` for a clean walk)."""
    await _ensure_listing_visible(db, listing_id, current_user)
    return await verify_listing_chain(db, listing_id)


@router.get("/snapshot/{sequence}", response_model=LedgerSnapshotRead)
async def get_snapshot_by_sequence(
    listing_id: uuid.UUID,
    sequence: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> LedgerSnapshotRead:
    """Specific snapshot by ``sequence_number``."""
    await _ensure_listing_visible(db, listing_id, current_user)
    row = (
        await db.execute(
            select(LedgerSnapshot).where(
                LedgerSnapshot.listing_id == listing_id,
                LedgerSnapshot.sequence_number == sequence,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found at that sequence.",
        )
    return _to_read(row)


# ─── Endpoint — manual trigger (creator-only, daily rate limited) ─────


@router.post(
    "/snapshot/now",
    response_model=LedgerSnapshotRead | SnapshotPayload,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_snapshot_now(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
    dry_run: Annotated[
        bool,
        Query(description="Return the payload the snapshot WOULD write; insert nothing."),
    ] = False,
) -> LedgerSnapshotRead | JSONResponse:
    """Manually trigger today's snapshot.

    Creator-only — only the listing's owner can advance the chain.
    Rate-limited to one snapshot per UTC day per listing via the
    ``UNIQUE (listing_id, snapshot_date)`` index; a duplicate call
    returns 409 with a clean error.

    Phase 4 swap-out: a scheduled job (Celery beat / k8s cron)
    drives this same code path daily; the manual trigger stays for
    backfill + admin tooling.
    """
    listing = (
        await db.execute(select(MarketplaceListing).where(MarketplaceListing.id == listing_id))
    ).scalar_one_or_none()
    if listing is None or listing.creator_id != current_user.id:
        # 404 (not 403) so non-owners can't enumerate listing ids.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )

    try:
        if dry_run:
            # Founder's pre-flight: same resolution + refusal rules, no insert.
            preview = await build_snapshot_preview(db, listing_id)
            logger.info(
                "marketplace.ledger.snapshot.dry_run",
                listing_id=str(listing_id),
                sequence=preview.sequence_number,
                creator_id=str(current_user.id),
            )
            # 200, not the decorator's 201: nothing was created.
            return JSONResponse(status_code=status.HTTP_200_OK, content=preview.model_dump())
        snapshot = await create_daily_snapshot(db, listing_id)
    except SnapshotAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except NothingToPublishError as exc:
        # Publish NOTHING rather than a zero: the chain is append-only.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NOTHING_TO_PUBLISH", "message": str(exc)},
        ) from exc
    except ListingNotFoundError as exc:  # pragma: no cover - guarded above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    logger.info(
        "marketplace.ledger.snapshot.triggered",
        listing_id=str(listing_id),
        sequence=snapshot.sequence_number,
        creator_id=str(current_user.id),
    )
    return _to_read(snapshot)


__all__ = ["router"]
