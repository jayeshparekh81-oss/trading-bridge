"""``create_daily_snapshot`` — DB-touching tests via aiosqlite.

Mirrors the marketplace API test setup: fresh in-memory DB per
test, seed a creator + listing + (optionally) some paper
sessions, then assert the snapshot row's content + chain link.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.auth.roles import ROLE_CREATOR
from app.db.base import Base
from app.db.models.ledger_snapshot import LedgerSnapshot
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.paper_session import PaperSession
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.strategy_engine.ledger.snapshots import (
    SnapshotAlreadyExistsError,
    create_daily_snapshot,
)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-ledger-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _seed_listing(
    db: AsyncSession,
    *,
    published_offset_days: int = 5,
) -> MarketplaceListing:
    creator = User(
        email=f"creator-{uuid.uuid4().hex[:8]}@x",
        password_hash="x",
        is_active=True,
        role=ROLE_CREATOR,
    )
    db.add(creator)
    await db.flush()
    strategy = Strategy(user_id=creator.id, name="for-ledger")
    db.add(strategy)
    await db.flush()
    listing = MarketplaceListing(
        strategy_id=strategy.id,
        creator_id=creator.id,
        title="Listing",
        description="d",
        price_inr=Decimal("0"),
        tags=[],
        status="published",
        published_at=datetime.now(UTC) - timedelta(days=published_offset_days),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


async def _seed_paper_session(
    db: AsyncSession,
    listing: MarketplaceListing,
    *,
    pnl: Decimal,
    trades: int,
    on_date: date,
) -> None:
    session = PaperSession(
        user_id=listing.creator_id,
        strategy_id=listing.strategy_id,
        session_date=on_date,
        is_complete=True,
        total_trades=trades,
        total_pnl=pnl,
        engine_strategy_id="test-engine-id",
    )
    db.add(session)
    await db.commit()


# ─── Genesis behaviour ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_genesis_snapshot_has_null_prior_hash(db: AsyncSession) -> None:
    listing = await _seed_listing(db)
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))
    assert snap.sequence_number == 1
    assert snap.prior_hash is None
    # Chain signature is SHA-256(data_hash|GENESIS) — always defined.
    assert len(snap.chain_signature) == 64


@pytest.mark.asyncio
async def test_second_snapshot_links_to_first_via_prior_hash(
    db: AsyncSession,
) -> None:
    listing = await _seed_listing(db)
    a = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))
    b = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 2))
    assert b.sequence_number == 2
    assert b.prior_hash == a.chain_signature
    # And the chain signature differs (different data + prior).
    assert a.chain_signature != b.chain_signature


@pytest.mark.asyncio
async def test_duplicate_day_snapshot_raises_already_exists(
    db: AsyncSession,
) -> None:
    listing = await _seed_listing(db)
    await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))
    with pytest.raises(SnapshotAlreadyExistsError):
        await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))


# ─── Performance payload ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_aggregates_paper_sessions(db: AsyncSession) -> None:
    """Two completed sessions: 100 + (-30) = 70 cumulative PnL,
    one win out of two → win_rate = 0.5, max_drawdown_pct = (100 - 70)/100*100 = 30 %."""
    listing = await _seed_listing(db)
    await _seed_paper_session(
        db, listing, pnl=Decimal("100"), trades=4, on_date=date(2026, 4, 28)
    )
    await _seed_paper_session(
        db, listing, pnl=Decimal("-30"), trades=2, on_date=date(2026, 4, 29)
    )
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))
    assert snap.cumulative_pnl_inr == Decimal("70.0000")
    assert snap.total_trades == 6
    assert snap.paper_trades_count == 6
    assert snap.win_rate == Decimal("0.5000")
    assert snap.max_drawdown_pct == Decimal("30.0000")


@pytest.mark.asyncio
async def test_snapshot_with_no_sessions_yields_zeros(
    db: AsyncSession,
) -> None:
    listing = await _seed_listing(db)
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))
    assert snap.cumulative_pnl_inr == Decimal("0.0000")
    assert snap.win_rate == Decimal("0.0000")
    assert snap.max_drawdown_pct == Decimal("0.0000")
    assert snap.total_trades == 0


@pytest.mark.asyncio
async def test_days_since_publish_increments_correctly(
    db: AsyncSession,
) -> None:
    """Listing published 5 days before snapshot_date → 5."""
    listing = await _seed_listing(db, published_offset_days=10)
    snap = await create_daily_snapshot(
        db,
        listing.id,
        snapshot_date=(listing.published_at.date() + timedelta(days=5)),
    )
    assert snap.days_since_publish == 5


# ─── Daily attestation row ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_creates_daily_attestation_row(
    db: AsyncSession,
) -> None:
    """Each snapshot also writes a ``daily_snapshot`` attestation
    with a non-null ``attestation_hash`` and (Phase 2) NULL
    polygon_tx_hash."""
    from sqlalchemy import select

    from app.db.models.ledger_attestation import LedgerAttestation

    listing = await _seed_listing(db)
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))

    rows = (
        await db.execute(
            select(LedgerAttestation).where(
                LedgerAttestation.snapshot_id == snap.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].attestation_type == "daily_snapshot"
    assert len(rows[0].attestation_hash) == 64
    assert rows[0].polygon_tx_hash is None  # Phase 4 will populate.


# ─── Ordered insert covers existing rows ─────────────────────────────


@pytest.mark.asyncio
async def test_third_snapshot_chains_through_two_prior_links(
    db: AsyncSession,
) -> None:
    listing = await _seed_listing(db)
    s1 = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 1))
    s2 = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 2))
    s3 = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 5, 3))
    # Sequence + prior chain must walk cleanly.
    assert s2.prior_hash == s1.chain_signature
    assert s3.prior_hash == s2.chain_signature
    assert [s1.sequence_number, s2.sequence_number, s3.sequence_number] == [1, 2, 3]


@pytest.mark.asyncio
async def test_snapshot_for_unknown_listing_raises(db: AsyncSession) -> None:
    from app.strategy_engine.ledger.snapshots import ListingNotFoundError

    bogus = uuid.uuid4()
    with pytest.raises(ListingNotFoundError):
        await create_daily_snapshot(db, bogus)


# Reference unused import to keep the symbol surface explicit.
_ = LedgerSnapshot
