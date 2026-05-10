"""Chain verification — happy path + tamper detection.

Builds a 3-snapshot chain, verifies it cleanly, then injects each
class of tamper (data field, prior_hash link, chain_signature
column, sequence gap) and asserts the verifier flags it on the
right sequence with the right reason.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import update
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
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.strategy_engine.ledger.snapshots import create_daily_snapshot
from app.strategy_engine.ledger.verification import verify_listing_chain


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-ledger-verify-{uuid.uuid4().hex}"
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


async def _build_three_snapshot_chain(db: AsyncSession) -> uuid.UUID:
    creator = User(
        email=f"c-{uuid.uuid4().hex[:8]}@x",
        password_hash="x",
        is_active=True,
        role=ROLE_CREATOR,
    )
    db.add(creator)
    await db.flush()
    strategy = Strategy(user_id=creator.id, name="for-verify")
    db.add(strategy)
    await db.flush()
    listing = MarketplaceListing(
        strategy_id=strategy.id,
        creator_id=creator.id,
        title="Verify",
        description="d",
        price_inr=Decimal("0"),
        tags=[],
        status="published",
        published_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    for offset in range(3):
        await create_daily_snapshot(
            db, listing.id, snapshot_date=date(2026, 5, 1) + timedelta(days=offset)
        )
    return listing.id


# ─── Happy path ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clean_chain_verifies_successfully(db: AsyncSession) -> None:
    listing_id = await _build_three_snapshot_chain(db)
    result = await verify_listing_chain(db, listing_id)
    assert result.is_chain_valid is True
    assert result.snapshots_verified == 3
    assert result.first_break_at_sequence is None


@pytest.mark.asyncio
async def test_empty_chain_verifies_as_valid(db: AsyncSession) -> None:
    """A listing with zero snapshots reports ``is_chain_valid=True``
    with ``snapshots_verified=0`` — there's nothing to break."""
    creator = User(
        email=f"empty-{uuid.uuid4().hex[:8]}@x",
        password_hash="x",
        is_active=True,
        role=ROLE_CREATOR,
    )
    db.add(creator)
    await db.flush()
    strategy = Strategy(user_id=creator.id, name="empty")
    db.add(strategy)
    await db.flush()
    listing = MarketplaceListing(
        strategy_id=strategy.id,
        creator_id=creator.id,
        title="Empty",
        description="d",
        price_inr=Decimal("0"),
        tags=[],
        status="published",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    result = await verify_listing_chain(db, listing.id)
    assert result.is_chain_valid is True
    assert result.snapshots_verified == 0


# ─── Tamper detection ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tampered_payload_field_breaks_chain_at_that_seq(
    db: AsyncSession,
) -> None:
    listing_id = await _build_three_snapshot_chain(db)
    # Tamper with sequence #2's cumulative_pnl — recomputed
    # data_hash will differ from the stored one.
    await db.execute(
        update(LedgerSnapshot)
        .where(
            LedgerSnapshot.listing_id == listing_id,
            LedgerSnapshot.sequence_number == 2,
        )
        .values(cumulative_pnl_inr=Decimal("999999"))
    )
    await db.commit()

    result = await verify_listing_chain(db, listing_id)
    assert result.is_chain_valid is False
    assert result.first_break_at_sequence == 2
    assert result.snapshots_verified == 1
    assert result.first_break_reason is not None
    assert "data_hash" in result.first_break_reason


@pytest.mark.asyncio
async def test_tampered_prior_hash_breaks_chain(db: AsyncSession) -> None:
    """If a malicious actor edited the prior_hash column to point at
    a different snapshot's chain_signature, the verifier flags it
    as a chain link break."""
    listing_id = await _build_three_snapshot_chain(db)
    await db.execute(
        update(LedgerSnapshot)
        .where(
            LedgerSnapshot.listing_id == listing_id,
            LedgerSnapshot.sequence_number == 3,
        )
        .values(prior_hash="0" * 64)
    )
    await db.commit()

    result = await verify_listing_chain(db, listing_id)
    assert result.is_chain_valid is False
    assert result.first_break_at_sequence == 3
    assert result.first_break_reason is not None
    assert "prior_hash" in result.first_break_reason


@pytest.mark.asyncio
async def test_tampered_chain_signature_breaks_chain(
    db: AsyncSession,
) -> None:
    """Editing chain_signature directly (without recomputing) trips
    the recomputed-signature check."""
    listing_id = await _build_three_snapshot_chain(db)
    await db.execute(
        update(LedgerSnapshot)
        .where(
            LedgerSnapshot.listing_id == listing_id,
            LedgerSnapshot.sequence_number == 1,
        )
        .values(chain_signature="f" * 64)
    )
    await db.commit()

    result = await verify_listing_chain(db, listing_id)
    assert result.is_chain_valid is False
    assert result.first_break_at_sequence == 1
    assert result.first_break_reason is not None
    assert "chain_signature" in result.first_break_reason


@pytest.mark.asyncio
async def test_sequence_gap_breaks_chain(db: AsyncSession) -> None:
    """Deleting snapshot #2 leaves a gap (1, 3) — verifier flags
    the missing sequence."""
    listing_id = await _build_three_snapshot_chain(db)
    from sqlalchemy import delete

    await db.execute(
        delete(LedgerSnapshot).where(
            LedgerSnapshot.listing_id == listing_id,
            LedgerSnapshot.sequence_number == 2,
        )
    )
    await db.commit()

    result = await verify_listing_chain(db, listing_id)
    assert result.is_chain_valid is False
    assert result.first_break_at_sequence == 3
    assert result.first_break_reason is not None
    assert "sequence" in result.first_break_reason
    assert result.snapshots_verified == 1


@pytest.mark.asyncio
async def test_unknown_listing_returns_clean_walk(db: AsyncSession) -> None:
    """Verifying a nonexistent listing doesn't 500 — it just
    reports zero snapshots verified, chain valid (vacuously)."""
    result = await verify_listing_chain(db, uuid.uuid4())
    assert result.is_chain_valid is True
    assert result.snapshots_verified == 0
