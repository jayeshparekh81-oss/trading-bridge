"""Subscriber signal feed — GET /api/marketplace/subscriptions/signals.

A subscriber sees the signals of the strategies they ACTIVELY subscribe to
(distinct from the owner-scoped GET /api/strategies/signals). Read-only +
black-box: signal-level fields + a server-computed validity window, never
strategy internals, never a broker call.

Self-contained (in-memory aiosqlite + dependency_overrides), mirroring the
marketplace/billing test harness. FK enforcement is off in this harness, so
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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router

_URL = "/api/marketplace/subscriptions/signals"


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-subfeed-{uuid.uuid4().hex}"
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


async def _seed_user(maker: async_sessionmaker[AsyncSession]) -> User:
    async with maker() as s:
        u = User(email=f"sf-{uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _seed_listing(
    maker: async_sessionmaker[AsyncSession],
    *, creator_id: uuid.UUID, strategy_id: uuid.UUID, title: str,
) -> uuid.UUID:
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
    maker: async_sessionmaker[AsyncSession],
    *, subscriber_id: uuid.UUID, listing_id: uuid.UUID, status: str = "active",
) -> None:
    async with maker() as s:
        s.add(MarketplaceSubscription(
            listing_id=listing_id, subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC), status=status,
            amount_paid_inr=Decimal("0"),
        ))
        await s.commit()


async def _seed_signal(
    maker: async_sessionmaker[AsyncSession],
    *, owner_id: uuid.UUID, strategy_id: uuid.UUID, symbol: str, action: str,
    payload: dict, received_at: datetime | None = None, status: str = "received",
) -> uuid.UUID:
    async with maker() as s:
        sig = StrategySignal(
            id=uuid.uuid4(), user_id=owner_id, strategy_id=strategy_id,
            raw_payload=payload, symbol=symbol, action=action, status=status,
            received_at=received_at or datetime.now(UTC),
        )
        s.add(sig)
        await s.commit()
        return sig.id


def _get(maker, user):
    return _client(maker, user).get(_URL)


# ═══════════════════════════════════════════════════════════════════════
# Scoping: sees subscribed, not unsubscribed; active only
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_subscriber_sees_subscribed_strategy_signals(db_maker):
    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat,
                                  title="Strategy Alpha")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing)
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="BSE-JUL2026-FUT", action="ENTRY",
                       payload={"price": "2437.50", "side": "long"})

    r = _get(db_maker, sub)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    row = body["signals"][0]
    assert row["symbol"] == "BSE-JUL2026-FUT"
    assert row["action"] == "ENTRY"
    assert row["entry"] == "2437.50"
    assert row["side"] == "long"
    assert row["listing_title"] == "Strategy Alpha"  # public listing name
    assert row["listing_id"] == str(listing)


@pytest.mark.asyncio
async def test_does_not_see_unsubscribed_strategy_signals(db_maker):
    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat_sub = uuid.uuid4()
    strat_other = uuid.uuid4()  # NOT subscribed
    listing = await _seed_listing(db_maker, creator_id=owner.id,
                                  strategy_id=strat_sub, title="Subscribed")
    # A different published listing the subscriber did NOT subscribe to.
    await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat_other,
                        title="Not subscribed")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing)
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat_sub,
                       symbol="SUB", action="ENTRY", payload={"price": "1"})
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat_other,
                       symbol="OTHER", action="ENTRY", payload={"price": "2"})

    body = _get(db_maker, sub).json()
    symbols = {s["symbol"] for s in body["signals"]}
    assert symbols == {"SUB"}          # only the subscribed strategy's signal
    assert "OTHER" not in symbols


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["cancelled", "expired", "pending"])
async def test_inactive_subscription_sees_nothing(db_maker, status):
    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat,
                                  title="X")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing,
                             status=status)
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="X", action="ENTRY", payload={"price": "1"})

    body = _get(db_maker, sub).json()
    assert body["count"] == 0 and body["signals"] == []


@pytest.mark.asyncio
async def test_no_subscriptions_returns_empty(db_maker):
    sub = await _seed_user(db_maker)
    body = _get(db_maker, sub).json()
    assert body == {"signals": [], "count": 0}


# ═══════════════════════════════════════════════════════════════════════
# Black-box: no internals; SL/target payload-only (never config-derived)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_no_strategy_internals_leaked(db_maker):
    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat,
                                  title="Alpha")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing)
    # Payload has entry price + a would-be-internal indicator blob, but NO sl/target.
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="X", action="ENTRY",
                       payload={"price": "100", "rsi": 71.4, "ema_fast": 99.2,
                                "strategy_json": {"secret": "rules"}})

    r = _get(db_maker, sub)
    row = r.json()["signals"][0]
    # Only the masked signal-level keys are present.
    assert set(row.keys()) == {
        "id", "listing_id", "listing_title", "symbol", "action", "side",
        "entry", "stop_loss", "target", "received_at", "status", "validity",
    }
    # SL/target NOT present (not in the payload) — never derived from config.
    assert row["stop_loss"] is None and row["target"] is None
    # No internals anywhere in the serialized response.
    text = r.text.lower()
    for leak in ("raw_payload", "strategy_json", "rsi", "ema_fast", "secret",
                 "indicator", "user_id", "hard_sl_pct"):
        assert leak not in text, f"leaked: {leak}"


@pytest.mark.asyncio
async def test_sl_target_shown_only_when_alert_carried_them(db_maker):
    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat,
                                  title="A")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing)
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="X", action="ENTRY",
                       payload={"price": "100", "sl": "95", "target": "115"})

    row = _get(db_maker, sub).json()["signals"][0]
    assert row["entry"] == "100"
    assert row["stop_loss"] == "95"    # explicit in the alert → shown
    assert row["target"] == "115"


# ═══════════════════════════════════════════════════════════════════════
# Server-computed validity (not client-trusted)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_entry_validity_5min_window(db_maker):
    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat,
                                  title="A")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing)
    # Fresh ENTRY (now) → valid; stale ENTRY (10 min ago) → lapsed.
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="FRESH", action="ENTRY", payload={"price": "1"},
                       received_at=datetime.now(UTC))
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="STALE", action="ENTRY", payload={"price": "1"},
                       received_at=datetime.now(UTC) - timedelta(minutes=10))

    by_symbol = {s["symbol"]: s for s in _get(db_maker, sub).json()["signals"]}
    fresh = by_symbol["FRESH"]["validity"]
    stale = by_symbol["STALE"]["validity"]
    assert fresh["window"] == "entry" and fresh["valid"] is True
    assert 0 < fresh["seconds_remaining"] <= 300
    assert stale["window"] == "entry" and stale["valid"] is False
    assert stale["seconds_remaining"] == 0


@pytest.mark.asyncio
async def test_exit_validity_is_eod_window(db_maker):
    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat,
                                  title="A")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing)
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="X", action="EXIT", payload={"price": "1"},
                       received_at=datetime.now(UTC))

    v = _get(db_maker, sub).json()["signals"][0]["validity"]
    assert v["window"] == "exit"       # EXIT → valid till EOD, not a 5-min window


# ═══════════════════════════════════════════════════════════════════════
# Read-only: places no order, no broker call
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_places_no_order_no_broker(db_maker, monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    sub = await _seed_user(db_maker)
    owner = await _seed_user(db_maker)
    strat = uuid.uuid4()
    listing = await _seed_listing(db_maker, creator_id=owner.id, strategy_id=strat,
                                  title="A")
    await _seed_subscription(db_maker, subscriber_id=sub.id, listing_id=listing)
    await _seed_signal(db_maker, owner_id=owner.id, strategy_id=strat,
                       symbol="X", action="ENTRY", payload={"price": "1"})

    r = _get(db_maker, sub)
    assert r.status_code == 200
    spy.assert_not_called()            # read-only — no order placed
