"""The scheduled drift task — the composition point, and Pause end-to-end.

Two things are proven here:

1. The task is REACHABLE and WIRED — registered, included, on the beat
   schedule — and DORMANT, because subscriber_drift_enabled defaults False.
   Scheduling it makes the machinery reachable; it enables nothing.

2. Pause reads and writes correctly end to end: the PATCH sets execution_mode
   and the GET reads it back, both directions.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace import router as marketplace_router

PAUSED = "offline"
RUNNING = "auto"


# ═══════════════════════════════════════════════════════════════════════
# 1. WIRED, NOT ENABLED
# ═══════════════════════════════════════════════════════════════════════


def test_the_task_is_registered_and_on_the_beat_schedule():
    from app.tasks.celery_app import celery_app

    name = "app.tasks.subscriber_drift_tasks.run_drift_pass"
    assert "app.tasks.subscriber_drift_tasks" in celery_app.conf.include

    entry = celery_app.conf.beat_schedule.get("subscriber-drift-pass")
    assert entry is not None, "the drift pass is not scheduled"
    assert entry["task"] == name


def test_the_cadence_is_market_hours_only_weekdays():
    """Every 5 min, UTC 03:00-10:59 Mon-Fri = IST 08:30-16:29. Outside those
    hours there is nothing to detect and no reason to spend a broker call."""
    from app.tasks.celery_app import celery_app

    sched = celery_app.conf.beat_schedule["subscriber-drift-pass"]["schedule"]
    assert sched.hour == set(range(3, 11)), sched.hour
    assert sched.day_of_week == {1, 2, 3, 4, 5}, sched.day_of_week
    assert sched.minute == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}


def test_the_flag_is_still_false_by_default():
    """Wired, not enabled. Shipping this turns nothing on."""
    from app.core.config import Settings

    assert Settings.model_fields["subscriber_drift_enabled"].default is False


def test_the_task_module_builds_the_fetcher_and_injects_it():
    """The worker must never construct a broker itself — the composition
    happens here, in one place, so there is one thing to audit."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app" / "tasks" / "subscriber_drift_tasks.py"
    ).read_text(encoding="utf-8")
    assert "make_subscriber_position_fetcher" in src
    assert "fetch_broker_positions=fetch" in src


# ═══════════════════════════════════════════════════════════════════════
# 2. Pause, end to end
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-pause-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    # Create ONLY the tables these tests touch. Base.metadata.create_all fails
    # on SQLite once any JSONB-bearing model is registered (strategy_templates
    # .config_json), which happens as soon as another test in the same session
    # imports the marketplace router.
    tables = [
        Base.metadata.tables[t]
        for t in (
            "users",
            "marketplace_subscriptions",
            "strategy_positions",
            "audit_logs",
        )
        if t in Base.metadata.tables
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


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


async def _sub(maker, *, subscriber_id, mode=RUNNING) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(), subscriber_id=subscriber_id,
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"), execution_mode=mode,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


@pytest.mark.asyncio
async def test_pause_writes_and_reads_back(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id, mode=RUNNING)
    c = _client(db_maker, u)

    # PAUSE
    res = c.patch(f"/api/marketplace/subscriptions/{sub_id}/settings",
                  json={"execution_mode": PAUSED})
    assert res.status_code == 200, res.text
    assert res.json()["execution_mode"] == PAUSED
    assert res.json()["applied"] is True

    # the GET agrees — a write that only the PATCH can see is not persisted
    got = c.get(f"/api/marketplace/subscriptions/{sub_id}/settings").json()
    assert got["execution_mode"] == PAUSED


@pytest.mark.asyncio
async def test_resume_writes_and_reads_back(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id, mode=PAUSED)
    c = _client(db_maker, u)

    res = c.patch(f"/api/marketplace/subscriptions/{sub_id}/settings",
                  json={"execution_mode": RUNNING})

    assert res.json()["execution_mode"] == RUNNING
    assert c.get(
        f"/api/marketplace/subscriptions/{sub_id}/settings"
    ).json()["execution_mode"] == RUNNING


@pytest.mark.asyncio
async def test_pausing_does_not_disturb_the_other_settings(db_maker):
    u = await _user(db_maker)
    sub_id = await _sub(db_maker, subscriber_id=u.id, mode=RUNNING)
    c = _client(db_maker, u)

    c.patch(f"/api/marketplace/subscriptions/{sub_id}/settings",
            json={"lots_override": 4, "direction_filter": "short"})
    res = c.patch(f"/api/marketplace/subscriptions/{sub_id}/settings",
                  json={"execution_mode": PAUSED})

    body = res.json()
    assert body["execution_mode"] == PAUSED
    assert body["lots_override"] == 4
    assert body["direction_filter"] == "short"


@pytest.mark.asyncio
async def test_another_customer_cannot_pause_my_subscription(db_maker):
    a = await _user(db_maker)
    b = await _user(db_maker)
    a_sub = await _sub(db_maker, subscriber_id=a.id, mode=RUNNING)

    res = _client(db_maker, b).patch(
        f"/api/marketplace/subscriptions/{a_sub}/settings",
        json={"execution_mode": PAUSED},
    )

    assert res.status_code == 404
    assert _client(db_maker, a).get(
        f"/api/marketplace/subscriptions/{a_sub}/settings"
    ).json()["execution_mode"] == RUNNING
