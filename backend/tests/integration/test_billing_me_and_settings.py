"""M3 backend reads/writes — ``GET /api/billing/me`` + per-subscriber settings.

Self-contained (in-memory aiosqlite + dependency_overrides), mirroring the
marketplace CRUD test harness. Covers:
    * billing/me reflects the entitlement (plan_status / is_active)
    * settings PATCH validates the even / 2-20 sizing rule (422 on odd / OOB)
    * CROSS-BRANCH SEAM (integration): the fan-out execution columns now exist,
      so the settings PATCH actually PERSISTS (applied=True) and the billing
      'paper' mode coexists with the fan-out vocab; GET round-trips the values
      and a fresh sub takes the fan-out defaults (execution_mode 'auto').
    * a non-owned subscription 404s
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.billing import router as billing_router
from app.api.deps import get_current_active_user, get_current_admin
from app.db.base import Base
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.razorpay_payment import RazorpayPayment
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-m3-{uuid.uuid4().hex}"
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


def _client(
    maker: async_sessionmaker[AsyncSession], user: User, *, admin: bool = False
) -> TestClient:
    app = FastAPI()
    app.include_router(billing_router)
    app.include_router(marketplace_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = lambda: user
    if admin:
        app.dependency_overrides[get_current_admin] = lambda: user
    return TestClient(app)


class _FakeSub:
    def __init__(self) -> None:
        self.cancel_calls: list[tuple[str, dict]] = []
        self._fetch: dict[str, dict] = {}

    def cancel(self, sub_id: str, data: dict) -> dict:
        self.cancel_calls.append((sub_id, data))
        return {"id": sub_id, "status": "cancelled"}

    def fetch(self, sub_id: str) -> dict:
        return self._fetch.get(sub_id, {"id": sub_id, "status": "active"})


class _FakeRzp:
    def __init__(self) -> None:
        self.subscription = _FakeSub()


def _use_fake(monkeypatch: object, fake: _FakeRzp) -> None:
    import app.services.razorpay_billing as rb
    from app.core import config as _config

    monkeypatch.setattr(rb, "get_razorpay_client", lambda: fake)  # type: ignore[attr-defined]
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_PUBLIC")  # type: ignore[attr-defined]
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "rzp_test_SECRET")  # type: ignore[attr-defined]
    _config.get_settings.cache_clear()


async def _seed_payment(
    maker: async_sessionmaker[AsyncSession], *, user_id: uuid.UUID, sub_id: str
) -> None:
    async with maker() as s:
        s.add(RazorpayPayment(
            user_id=user_id, kind="platform_plan",
            razorpay_subscription_id=sub_id, status="active",
        ))
        await s.commit()


async def _seed_paid_sub(
    maker: async_sessionmaker[AsyncSession],
    *, subscriber_id: uuid.UUID, listing_id: uuid.UUID, sub_id: str,
) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=listing_id, subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("499"), razorpay_subscription_id=sub_id,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def _seed_user(maker: async_sessionmaker[AsyncSession], **kw: object) -> User:
    async with maker() as s:
        u = User(
            email=f"m3-{uuid.uuid4().hex}@t.com",
            password_hash="x",
            is_active=True,
            **kw,
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _seed_sub(
    maker: async_sessionmaker[AsyncSession], subscriber_id: uuid.UUID
) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(),
            subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC),
            status="active",
            amount_paid_inr=Decimal("499"),
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


# ── billing/me ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_billing_me_reflects_active_entitlement(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(
        db_maker,
        plan_status="active",
        plan_expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    with _client(db_maker, user) as client:
        r = client.get("/api/billing/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan_status"] == "active"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_billing_me_free_user_is_inactive(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker, plan_status="none")
    with _client(db_maker, user) as client:
        r = client.get("/api/billing/me")
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


# ── subscription settings ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_settings_patch_rejects_odd_lots(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 3},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_settings_patch_rejects_below_minimum(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 1},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_settings_patch_rejects_bad_execution_mode(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"execution_mode": "banana"},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_settings_patch_persists_post_fanout_merge(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """CROSS-BRANCH SEAM: on the INTEGRATION branch the fan-out execution
    columns exist, so the M3 settings PATCH (previously guarded as
    ``pending_fanout_merge``) now ACTUALLY PERSISTS — applied=True, and a
    follow-up GET reads the stored values back."""
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 4, "execution_mode": "one_click", "is_paper": False},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["lots_override"] == 4
        assert body["execution_mode"] == "one_click"
        assert body["is_paper"] is False
        assert body["applied"] is True            # columns now present -> persisted
        assert body["pending_fanout_merge"] is False
        g = client.get(f"/api/marketplace/subscriptions/{sub_id}/settings").json()
    assert g["lots_override"] == 4
    assert g["execution_mode"] == "one_click"
    assert g["is_paper"] is False
    assert g["applied"] is True


@pytest.mark.asyncio
async def test_settings_patch_persists_paper_mode_seam(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """The billing M3 vocab value ``'paper'`` coexists with the fan-out column
    (widened by migration 038) — it PATCHes + persists cleanly post-merge."""
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"execution_mode": "paper", "is_paper": True},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["execution_mode"] == "paper"
    assert body["applied"] is True


@pytest.mark.asyncio
async def test_settings_get_defaults_post_merge(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Post-merge a fresh sub takes the fan-out column defaults: execution_mode
    'auto' + is_paper True (paper-only), applied=True (columns present)."""
    user = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, user.id)
    with _client(db_maker, user) as client:
        r = client.get(f"/api/marketplace/subscriptions/{sub_id}/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["execution_mode"] == "auto"   # fan-out server_default
    assert body["is_paper"] is True           # paper-only by default
    assert body["lots_override"] is None
    assert body["applied"] is True


@pytest.mark.asyncio
async def test_settings_patch_on_unowned_subscription_404s(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    owner = await _seed_user(db_maker)
    other = await _seed_user(db_maker)
    sub_id = await _seed_sub(db_maker, owner.id)
    with _client(db_maker, other) as client:
        r = client.patch(
            f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 4},
        )
    assert r.status_code == 404, r.text


# ── M4 lifecycle endpoints ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_endpoint_schedules_cycle_end(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: object
) -> None:
    fake = _FakeRzp()
    _use_fake(monkeypatch, fake)
    user = await _seed_user(db_maker, plan_status="active", razorpay_subscription_id="sub_E")
    await _seed_payment(db_maker, user_id=user.id, sub_id="sub_E")
    with _client(db_maker, user) as client:
        r = client.post("/api/billing/cancel", json={"at_cycle_end": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["at_cycle_end"] is True
    assert body["plan_status"] == "active"  # access retained until period end
    assert fake.subscription.cancel_calls == [("sub_E", {"cancel_at_cycle_end": 1})]
    from app.core import config as _config

    _config.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_cancel_endpoint_no_subscription_404(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: object
) -> None:
    fake = _FakeRzp()
    _use_fake(monkeypatch, fake)
    user = await _seed_user(db_maker, plan_status="none")
    with _client(db_maker, user) as client:
        r = client.post("/api/billing/cancel", json={})
    assert r.status_code == 404, r.text
    from app.core import config as _config

    _config.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_marketplace_paid_unsubscribe_schedules_cycle_end(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: object
) -> None:
    fake = _FakeRzp()
    _use_fake(monkeypatch, fake)
    user = await _seed_user(db_maker)
    listing_id = uuid.uuid4()
    await _seed_paid_sub(
        db_maker, subscriber_id=user.id, listing_id=listing_id, sub_id="sub_MK"
    )
    with _client(db_maker, user) as client:
        r = client.delete(f"/api/marketplace/listings/{listing_id}/subscribe")
    assert r.status_code == 200, r.text  # paid -> scheduled (not 204)
    body = r.json()
    assert body["scheduled_cancel"] is True
    assert body["status"] == "active"  # access retained until period end
    assert fake.subscription.cancel_calls == [("sub_MK", {"cancel_at_cycle_end": 1})]
    from app.core import config as _config

    _config.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_reconcile_reports_drift(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: object
) -> None:
    fake = _FakeRzp()
    fake.subscription._fetch["sub_DR"] = {"id": "sub_DR", "status": "cancelled"}
    _use_fake(monkeypatch, fake)
    user = await _seed_user(db_maker, plan_status="active", razorpay_subscription_id="sub_DR")
    await _seed_payment(db_maker, user_id=user.id, sub_id="sub_DR")
    with _client(db_maker, user, admin=True) as client:
        r = client.get("/api/billing/admin/reconcile", params={"user_id": str(user.id)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["drift_count"] == 1
    assert body["reports"][0]["gateway_status"] == "cancelled"
    assert body["reports"][0]["local_status"] == "active"
    from app.core import config as _config

    _config.get_settings.cache_clear()
