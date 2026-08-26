"""Subscriber confirm / take-trade — POST
/api/marketplace/subscriptions/signals/{signal_id}/confirm.

LIVE-MONEY-CRITICAL, PAPER-GATED. A subscriber confirms ONE signal from a
strategy they ACTIVELY subscribe to → a PAPER (simulated) fill is recorded.
Kill-switch-class guarantees under test: own-subscription scoping, server-side
validity re-check, idempotency (one fill, not two), and NEVER a real broker
call (paper primitive only) — even when "real-eligible".

Self-contained (in-memory aiosqlite + dependency_overrides). FK enforcement is
off, so the subscription carries an explicit ``broker_credential_id`` and
strategy_ids are plain UUIDs (no Strategy rows needed).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router


def _url(signal_id) -> str:
    return f"/api/marketplace/subscriptions/signals/{signal_id}/confirm"


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-confirm-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


def _client(maker: async_sessionmaker[AsyncSession], user: User) -> TestClient:
    app = FastAPI()
    app.include_router(marketplace_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: user
    return TestClient(app)


async def _seed_user(maker) -> User:
    async with maker() as s:
        u = User(email=f"c-{uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _seed_listing(maker, *, creator_id, strategy_id, title="A") -> uuid.UUID:
    async with maker() as s:
        listing = MarketplaceListing(
            creator_id=creator_id, strategy_id=strategy_id,
            title=title, status="published",
        )
        s.add(listing)
        await s.commit()
        await s.refresh(listing)
        return listing.id


async def _seed_subscription(
    maker, *, subscriber_id, listing_id, status="active",
    is_paper=True, lots_override=None,
) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=listing_id, subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC), status=status,
            amount_paid_inr=Decimal("0"),
            is_paper=is_paper, lots_override=lots_override,
            broker_credential_id=uuid.uuid4(),  # paper placeholder anchor
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def _seed_signal(
    maker, *, owner_id, strategy_id, action="ENTRY",
    payload=None, received_at=None,
) -> uuid.UUID:
    async with maker() as s:
        sig = StrategySignal(
            id=uuid.uuid4(), user_id=owner_id, strategy_id=strategy_id,
            raw_payload=payload or {"price": "100"}, symbol="BSE-FUT",
            action=action, status="received",
            received_at=received_at or datetime.now(UTC),
        )
        s.add(sig)
        await s.commit()
        return sig.id


async def _exec_count(maker, *, signal_id, subscription_id) -> int:
    async with maker() as s:
        return (
            await s.execute(
                select(func.count()).select_from(StrategyExecution).where(
                    StrategyExecution.signal_id == signal_id,
                    StrategyExecution.subscription_id == subscription_id,
                )
            )
        ).scalar_one()


async def _scene(maker, *, is_paper=True, lots_override=None, action="ENTRY",
                 received_at=None, sub_status="active"):
    """subscriber + owner + listing + active sub + one signal → ids."""
    sub_u = await _seed_user(maker)
    owner = await _seed_user(maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(maker, creator_id=owner.id, strategy_id=strat)
    sub_id = await _seed_subscription(
        maker, subscriber_id=sub_u.id, listing_id=listing, status=sub_status,
        is_paper=is_paper, lots_override=lots_override)
    sig_id = await _seed_signal(
        maker, owner_id=owner.id, strategy_id=strat, action=action,
        received_at=received_at)
    return sub_u, sub_id, strat, sig_id


# ═══════════════════════════════════════════════════════════════════════
# Happy path — paper fill
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_confirm_on_own_subscription_records_paper_fill(db_maker):
    sub_u, sub_id, _strat, sig_id = await _scene(db_maker, lots_override=4)
    r = _client(db_maker, sub_u).post(_url(sig_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "confirmed_paper"
    assert body["placed_real"] is False
    assert body["quantity"] == 4
    assert body["price"] == "100"
    assert body["broker_order_id"].startswith("PAPER-")
    assert body["validity"]["valid"] is True
    # exactly one execution row persisted for (signal, subscription)
    assert await _exec_count(db_maker, signal_id=sig_id, subscription_id=sub_id) == 1


# ═══════════════════════════════════════════════════════════════════════
# Scoping — must actively subscribe
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_confirm_on_non_subscribed_strategy_rejected(db_maker):
    # A signal on a strategy the caller does NOT subscribe to.
    caller = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    other_strat = uuid.uuid4()
    await _seed_listing(db_maker, creator_id=owner.id, strategy_id=other_strat)
    sig_id = await _seed_signal(db_maker, owner_id=owner.id, strategy_id=other_strat)

    r = _client(db_maker, caller).post(_url(sig_id))
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_confirm_with_cancelled_subscription_rejected(db_maker):
    sub_u, _sub_id, _strat, sig_id = await _scene(db_maker, sub_status="cancelled")
    r = _client(db_maker, sub_u).post(_url(sig_id))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_confirm_missing_signal_404(db_maker):
    caller = await _seed_user(db_maker)
    r = _client(db_maker, caller).post(_url(uuid.uuid4()))
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Server-side validity re-check
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_lapsed_entry_signal_rejected(db_maker):
    # ENTRY received 10 min ago → past the 5-min window → 409.
    sub_u, sub_id, _strat, sig_id = await _scene(
        db_maker, action="ENTRY",
        received_at=datetime.now(UTC) - timedelta(minutes=10))
    r = _client(db_maker, sub_u).post(_url(sig_id))
    assert r.status_code == 409, r.text
    assert "laps" in r.text.lower()
    # nothing was placed
    assert await _exec_count(db_maker, signal_id=sig_id, subscription_id=sub_id) == 0


@pytest.mark.asyncio
async def test_fresh_entry_valid_server_computed(db_maker):
    # Server recomputes validity — a fresh ENTRY is valid (no client input at all).
    sub_u, _sub_id, _strat, sig_id = await _scene(
        db_maker, action="ENTRY", received_at=datetime.now(UTC))
    body = _client(db_maker, sub_u).post(_url(sig_id)).json()
    assert body["validity"]["window"] == "entry"
    assert body["validity"]["valid"] is True


# ═══════════════════════════════════════════════════════════════════════
# Idempotency — one fill, not two
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_double_confirm_is_idempotent(db_maker):
    sub_u, sub_id, _strat, sig_id = await _scene(db_maker)
    client = _client(db_maker, sub_u)

    first = client.post(_url(sig_id))
    second = client.post(_url(sig_id))

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["status"] == "confirmed_paper"
    assert second.json()["status"] == "already_confirmed"
    # SAME execution, and only ONE row — no second fill.
    assert first.json()["execution_id"] == second.json()["execution_id"]
    assert await _exec_count(db_maker, signal_id=sig_id, subscription_id=sub_id) == 1


# ═══════════════════════════════════════════════════════════════════════
# PAPER-GATE — never a real broker order (the whole safety point)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paper_flags_off_no_real_broker_call(db_maker, monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    sub_u, _sub_id, _strat, sig_id = await _scene(db_maker, is_paper=True)
    body = _client(db_maker, sub_u).post(_url(sig_id)).json()

    assert body["placed_real"] is False
    spy.assert_not_called()             # no real order, ever


@pytest.mark.asyncio
async def test_real_eligible_still_records_paper_no_broker(db_maker, monkeypatch):
    """Even when is_paper=false AND the fan-out flag is ON (real-eligible), this
    endpoint records PAPER and calls no broker — the real path is NOT wired."""
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    monkeypatch.setattr(get_settings(), "marketplace_fanout_enabled", True)

    sub_u, _sub_id, _strat, sig_id = await _scene(db_maker, is_paper=False)
    r = _client(db_maker, sub_u).post(_url(sig_id))
    body = r.json()

    assert r.status_code == 200
    assert body["placed_real"] is False        # STILL paper — no real order
    assert body["broker_order_id"].startswith("PAPER-")
    assert "not wired" in body["note"].lower()
    spy.assert_not_called()
