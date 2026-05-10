"""Cached strategy scores — TTL semantics for the SafetyChain.

Migration 012 added ``last_trust_score`` / ``last_truth_score`` /
``last_scores_at`` to the ``strategies`` table.
:func:`get_cached_scores` is the read path the live-orders SafetyChain
calls before placing every live order. These tests pin every edge
case the chain depends on:

    * Strategy id missing             → ``None``
    * Row exists, never backtested    → ``None`` (NULL columns)
    * Partial write (one column null) → ``None`` (defence-in-depth)
    * Fresh scores (< 24h)            → snapshot returned, age computed
    * Stale scores (> 24h)            → ``None``
    * Naive timestamp (sqlite quirk)  → coerced to UTC, no exception
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.strategy_engine.live_orders.strategy_scores import (
    SCORES_TTL,
    StrategyScoresSnapshot,
    get_cached_scores,
)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def user(db: AsyncSession) -> User:
    u = User(email="scores@x", password_hash="p", is_active=True)
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def strategy(db: AsyncSession, user: User) -> Strategy:
    s = Strategy(user_id=user.id, name="scored", is_active=True)
    db.add(s)
    await db.flush()
    return s


# ─── 1. Missing / NULL paths ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_none_when_strategy_absent(db: AsyncSession) -> None:
    assert await get_cached_scores(db, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_returns_none_when_never_backtested(
    db: AsyncSession, strategy: Strategy
) -> None:
    """Fresh strategy row — three score columns are NULL."""
    assert strategy.last_trust_score is None
    assert strategy.last_truth_score is None
    assert strategy.last_scores_at is None
    assert await get_cached_scores(db, strategy.id) is None


@pytest.mark.asyncio
async def test_returns_none_when_partial_write(
    db: AsyncSession, strategy: Strategy
) -> None:
    """One column populated but another NULL — defence-in-depth reject."""
    strategy.last_trust_score = Decimal("75.00")
    strategy.last_scores_at = datetime.now(UTC)
    # last_truth_score stays NULL.
    await db.flush()

    assert await get_cached_scores(db, strategy.id) is None


# ─── 2. Fresh scores ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_snapshot_when_scores_fresh(
    db: AsyncSession, strategy: Strategy
) -> None:
    computed = datetime.now(UTC) - timedelta(hours=1)
    strategy.last_trust_score = Decimal("82.50")
    strategy.last_truth_score = Decimal("63.25")
    strategy.last_scores_at = computed
    await db.flush()

    snap = await get_cached_scores(db, strategy.id)
    assert snap is not None
    assert isinstance(snap, StrategyScoresSnapshot)
    assert snap.trust_score == 82.5
    assert snap.truth_score == 63.25
    assert 0.5 < snap.age_hours < 1.5  # ~1h ago


@pytest.mark.asyncio
async def test_just_under_ttl_still_fresh(
    db: AsyncSession, strategy: Strategy
) -> None:
    """Scores at TTL minus one minute are still considered fresh."""
    computed = datetime.now(UTC) - SCORES_TTL + timedelta(minutes=1)
    strategy.last_trust_score = Decimal("70.00")
    strategy.last_truth_score = Decimal("55.00")
    strategy.last_scores_at = computed
    await db.flush()

    snap = await get_cached_scores(db, strategy.id)
    assert snap is not None


# ─── 3. Stale scores ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_none_when_scores_stale(
    db: AsyncSession, strategy: Strategy
) -> None:
    """Scores older than 24h → SafetyChain blocks with 'refresh' message."""
    computed = datetime.now(UTC) - SCORES_TTL - timedelta(minutes=1)
    strategy.last_trust_score = Decimal("90.00")
    strategy.last_truth_score = Decimal("80.00")
    strategy.last_scores_at = computed
    await db.flush()

    assert await get_cached_scores(db, strategy.id) is None


# ─── 4. Naive timestamp coercion ──────────────────────────────────────


@pytest.mark.asyncio
async def test_naive_timestamp_is_coerced_to_utc(
    db: AsyncSession, strategy: Strategy
) -> None:
    """SQLite stores ``DateTime(timezone=True)`` as naive — the helper
    must coerce to UTC rather than raise on the comparison."""
    aware = datetime.now(UTC) - timedelta(hours=2)
    naive = aware.replace(tzinfo=None)
    strategy.last_trust_score = Decimal("75.00")
    strategy.last_truth_score = Decimal("60.00")
    strategy.last_scores_at = naive
    await db.flush()

    snap = await get_cached_scores(db, strategy.id)
    assert snap is not None
    assert snap.computed_at.tzinfo is not None
