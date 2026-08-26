"""Emergency exit — POST /api/marketplace/subscriptions/{id}/close-position.

The FIRST endpoint in the subscriber stack that ACTS rather than withholding
action, so the guards are the test surface:

  * own flag (emergency_exit_enabled), default OFF
  * ownership asserted twice — customer A can NEVER close B's position
  * Redis idempotency claim (a read-then-act status check cannot survive two
    concurrent clicks), FAIL CLOSED
  * a partial is NEVER reported as success, and a position that did not close
    stays `open` — never mark done what was not closed
  * after a close, a later EXIT signal is a no-op
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_position import StrategyPosition
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router


def _url(sub_id):
    return f"/api/marketplace/subscriptions/{sub_id}/close-position"


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-exit-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest.fixture
def exit_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "emergency_exit_enabled", True)
    monkeypatch.setattr(get_settings(), "marketplace_fanout_enabled", True)


@pytest.fixture
def fresh_idem(monkeypatch):
    """Idempotency slot always free unless a test says otherwise."""
    from app.core import redis_client

    async def _claim(_key, ttl_seconds=None):
        return True

    monkeypatch.setattr(redis_client, "set_idempotency_key", _claim)


def _client(maker, user: User) -> TestClient:
    app = FastAPI()
    app.include_router(marketplace_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: user
    return TestClient(app)


async def _user(maker) -> User:
    async with maker() as s:
        u = User(email=f"u-{uuid.uuid4().hex}@t.com", password_hash="x", is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _scene(maker, *, user, is_paper=True, pos_status="open"):
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(), subscriber_id=user.id,
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"), execution_mode="auto",
            is_paper=is_paper,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        pos = StrategyPosition(
            strategy_id=uuid.uuid4(), subscription_id=sub.id, user_id=user.id,
            symbol="BSE-AUG2026-FUT", side="buy", total_quantity=2,
            remaining_quantity=2, status=pos_status, opened_at=datetime.now(UTC),
            broker_credential_id=uuid.uuid4(),
        )
        s.add(pos)
        await s.commit()
        await s.refresh(pos)
        return sub.id, pos.id


async def _pos(maker, pos_id) -> StrategyPosition:
    async with maker() as s:
        return (await s.execute(
            select(StrategyPosition).where(StrategyPosition.id == pos_id))).scalar_one()


# ═══════════════════════════════════════════════════════════════════════
# Flag
# ═══════════════════════════════════════════════════════════════════════


def test_flag_defaults_off():
    assert get_settings().emergency_exit_enabled is False


@pytest.mark.asyncio
async def test_dormant_when_flag_off_closes_nothing(db_maker, fresh_idem):
    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u)

    r = _client(db_maker, u).post(_url(sub_id), json={"position_id": str(pos_id)})
    body = r.json()

    assert body["status"] == "dormant"
    assert body["placed_real"] is False
    assert (await _pos(db_maker, pos_id)).status == "open"   # untouched


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ OWNERSHIP — A can never close B's position
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_customer_cannot_close_another_customers_position(
    db_maker, exit_on, fresh_idem
):
    alice = await _user(db_maker)
    bob = await _user(db_maker)
    bob_sub, bob_pos = await _scene(db_maker, user=bob)

    # Alice aims at Bob's subscription + position.
    r = _client(db_maker, alice).post(
        _url(bob_sub), json={"position_id": str(bob_pos)})

    assert r.status_code == 404                              # not even confirmed
    assert (await _pos(db_maker, bob_pos)).status == "open"  # untouched


@pytest.mark.asyncio
async def test_cannot_close_a_position_from_another_subscription(
    db_maker, exit_on, fresh_idem
):
    """Own subscription, but a position belonging to a different one."""
    alice = await _user(db_maker)
    bob = await _user(db_maker)
    alice_sub, _ = await _scene(db_maker, user=alice)
    _bob_sub, bob_pos = await _scene(db_maker, user=bob)

    r = _client(db_maker, alice).post(
        _url(alice_sub), json={"position_id": str(bob_pos)})

    assert r.status_code == 404
    assert (await _pos(db_maker, bob_pos)).status == "open"


@pytest.mark.asyncio
async def test_unknown_subscription_is_404(db_maker, exit_on, fresh_idem):
    u = await _user(db_maker)
    r = _client(db_maker, u).post(
        _url(uuid.uuid4()), json={"position_id": str(uuid.uuid4())})
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Paper close
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paper_close_marks_position_closed_and_places_no_real_order(
    db_maker, exit_on, fresh_idem, monkeypatch
):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u, is_paper=True)

    body = _client(db_maker, u).post(
        _url(sub_id), json={"position_id": str(pos_id)}).json()

    assert body["status"] == "closed"
    assert body["placed_real"] is False
    assert "PAPER" in body["note"]
    spy.assert_not_called()

    row = await _pos(db_maker, pos_id)
    assert row.status == "closed"
    assert row.remaining_quantity == 0


@pytest.mark.asyncio
async def test_already_closed_is_reported_not_reclosed(db_maker, exit_on, fresh_idem):
    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u, pos_status="closed")
    body = _client(db_maker, u).post(
        _url(sub_id), json={"position_id": str(pos_id)}).json()
    assert body["status"] == "already_flat"
    assert body["placed_real"] is False


# ═══════════════════════════════════════════════════════════════════════
# Idempotency — the claim, not the status read
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sequential_double_submit_closes_exactly_once(
    db_maker, exit_on, monkeypatch
):
    """A normal double-click: the second sees a closed row and does nothing.

    The safety property is "closed once", not "second call errors" — the second
    request is correctly a benign already_flat.
    """
    from app.services.kill_switch_service import KillSwitchService

    calls = {"n": 0}
    real = KillSwitchService.kill_subscriber

    async def _counting(self, session, subscription_id, **kw):
        calls["n"] += 1
        return await real(self, session, subscription_id, **kw)

    monkeypatch.setattr(KillSwitchService, "kill_subscriber", _counting)

    from app.core import redis_client

    async def _claim(_key, ttl_seconds=None):
        return True                      # claim never blocks; status check does

    monkeypatch.setattr(redis_client, "set_idempotency_key", _claim)

    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u)
    client = _client(db_maker, u)

    first = client.post(_url(sub_id), json={"position_id": str(pos_id)})
    second = client.post(_url(sub_id), json={"position_id": str(pos_id)})

    assert first.json()["status"] == "closed"
    assert second.json()["status"] == "already_flat"
    assert calls["n"] == 1, "the close primitive ran twice"


@pytest.mark.asyncio
async def test_concurrent_double_submit_is_refused_by_the_claim(
    db_maker, exit_on, monkeypatch
):
    """THE window the claim exists for: both requests pass the status read.

    Simulated by a close that leaves the row `open`, so the second request's
    read-then-act check cannot save us — only the claim can.
    """
    from app.core import redis_client
    from app.services.kill_switch_service import KillSwitchService

    async def _noop(_self, _session, _subscription_id, **_kw):
        # Leaves the position `open` — as if the first close were still in
        # flight when the second request arrived.
        return {"status": "partial", "closed": 0, "errors": ["in flight"]}

    monkeypatch.setattr(KillSwitchService, "kill_subscriber", _noop)

    seen: set[str] = set()

    async def _claim(key, ttl_seconds=None):
        if key in seen:
            return False
        seen.add(key)
        return True

    monkeypatch.setattr(redis_client, "set_idempotency_key", _claim)

    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u)
    client = _client(db_maker, u)

    first = client.post(_url(sub_id), json={"position_id": str(pos_id)})
    second = client.post(_url(sub_id), json={"position_id": str(pos_id)})

    assert first.status_code == 200            # got through
    assert second.status_code == 409           # refused BY THE CLAIM
    assert "already in progress" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_redis_outage_fails_closed_and_changes_nothing(
    db_maker, exit_on, monkeypatch
):
    """A duplicate close could open an unwanted short — so refuse instead."""
    from app.core import redis_client

    async def _boom(_key, ttl_seconds=None):
        raise ConnectionError("redis down")

    monkeypatch.setattr(redis_client, "set_idempotency_key", _boom)

    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u)

    r = _client(db_maker, u).post(_url(sub_id), json={"position_id": str(pos_id)})

    assert r.status_code == 503
    assert (await _pos(db_maker, pos_id)).status == "open"   # nothing closed


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ Partial failure — never success, never mark done what did not close
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_partial_is_not_reported_as_success_and_row_stays_open(
    db_maker, exit_on, fresh_idem, monkeypatch
):
    """The broker close fails: the row must stay `open` and status must not
    say closed — otherwise a later exit signal is silently disarmed on a
    still-live position."""
    from app.services.kill_switch_service import KillSwitchService

    async def _fail(_self, _session, _subscription_id, **_kw):
        return {"status": "partial", "closed": 0,
                "errors": ["broker rejected close for BSE-AUG2026-FUT"]}

    monkeypatch.setattr(KillSwitchService, "kill_subscriber", _fail)

    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u)

    body = _client(db_maker, u).post(
        _url(sub_id), json={"position_id": str(pos_id)}).json()

    assert body["status"] != "closed"                    # NOT success
    assert body["positions"][0]["outcome"] == "not_closed"
    assert body["positions"][0]["quantity_closed"] == 0
    assert body["errors"]                                 # told verbatim
    assert "check your broker" in body["note"].lower()
    assert (await _pos(db_maker, pos_id)).status == "open"   # still live


@pytest.mark.asyncio
async def test_failed_close_reports_failed(db_maker, exit_on, fresh_idem, monkeypatch):
    from app.services.kill_switch_service import KillSwitchService

    async def _fail(_self, _session, _subscription_id, **_kw):
        return {"status": "failed", "closed": 0, "errors": ["session expired"]}

    monkeypatch.setattr(KillSwitchService, "kill_subscriber", _fail)

    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u)
    body = _client(db_maker, u).post(
        _url(sub_id), json={"position_id": str(pos_id)}).json()

    assert body["status"] == "failed"
    assert body["placed_real"] is False
    assert (await _pos(db_maker, pos_id)).status == "open"


# ═══════════════════════════════════════════════════════════════════════
# THE POINT — a later EXIT signal is a no-op after the close
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_later_exit_signal_is_a_noop_after_the_close(
    db_maker, exit_on, fresh_idem
):
    """After closing here, the fan-out's position lookup must find nothing —
    so a PARTIAL / EXIT / SL_HIT places no order."""
    from app.services.marketplace_fanout import PaperPositionProvider

    u = await _user(db_maker)
    sub_id, pos_id = await _scene(db_maker, user=u)
    row_before = await _pos(db_maker, pos_id)

    async with db_maker() as s:
        found = await PaperPositionProvider().find_open(
            s, strategy_id=row_before.strategy_id, subscription_id=sub_id)
    assert found is not None                       # visible before the close

    _client(db_maker, u).post(_url(sub_id), json={"position_id": str(pos_id)})

    async with db_maker() as s:
        found_after = await PaperPositionProvider().find_open(
            s, strategy_id=row_before.strategy_id, subscription_id=sub_id)
    assert found_after is None                     # -> skipped_no_position
