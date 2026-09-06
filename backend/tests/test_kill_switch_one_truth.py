"""One brake, one pedal — Simple's "Sab band" and Pro's kill switch are ONE fact.

Until 2026-09-06 they were two separate brakes. ``POST /api/strategies/kill-switch``
(Simple's big red button) closed the strategy engine's own positions and rejected
in-flight signals, but never flipped the platform gate — so ``GET /api/kill-switch/
status`` still answered ACTIVE. A customer tapped "Sab band", was told
"Sab band ho gaya", switched to Pro and read "Chalu hai — naye signals par order
ja sakte hain".

These tests pin the founder's three cases:
    trip from Simple -> Pro shows tripped
    trip from Pro    -> Simple shows tripped   (both read one status endpoint)
    reset once       -> both clear

Plus the two properties that make it safe to ship: the endpoint stays idempotent,
and it does NOT reach into the broker (Pro gates that chain behind a confirmation
token, and "Sab band" is a single unconfirmed tap).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_current_active_user
from app.api.kill_switch import router as kill_switch_router
from app.api.strategy_positions import router as strategy_positions_router
from app.core import redis_client
from app.db.base import Base
from app.db.models.kill_switch import KillSwitchConfig, KillSwitchEvent
from app.db.models.user import User
from app.db.session import get_session

SIMPLE_TRIP = "/api/strategies/kill-switch"
PRO_STATUS = "/api/kill-switch/status"
PRO_TRIP = "/api/kill-switch/trip"
PRO_RESET = "/api/kill-switch/reset"
PRO_TOKEN = "/api/kill-switch/reset-token"


@pytest_asyncio.fixture
async def maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest_asyncio.fixture
async def user(maker: async_sessionmaker[AsyncSession]) -> User:
    async with maker() as s:
        u = User(email="simple@x", password_hash="p", is_active=True)
        s.add(u)
        await s.flush()
        s.add(
            KillSwitchConfig(
                user_id=u.id,
                max_daily_loss_inr=Decimal("1000"),
                max_daily_trades=5,
                enabled=True,
                # Layer 1 gate: keeps Pro's trip off the broker in this test, so
                # the assertions are about the GATE, not about broker plumbing.
                auto_square_off=False,
            )
        )
        await s.commit()
        return u


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    maker: async_sessionmaker[AsyncSession],
    user: User,
) -> TestClient:
    fake = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)

    app = FastAPI()
    app.include_router(strategy_positions_router)
    app.include_router(kill_switch_router)

    async def _session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    async def _user() -> User:
        return user

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_active_user] = _user
    return TestClient(app)


def _state(c: TestClient) -> str:
    r = c.get(PRO_STATUS)
    assert r.status_code == 200, r.text
    return r.json()["state"]


def _token(c: TestClient) -> str:
    """POST /reset-token answers {"confirmation_token": "..."} — both /trip and
    /reset require it, so a stray dashboard click cannot fire the chain."""
    body = c.post(PRO_TOKEN).json()
    return body["confirmation_token"]


def _reset(c: TestClient) -> Any:
    return c.post(PRO_RESET, json={"confirmation_token": _token(c)})


class TestOneTruth:
    def test_simple_trip_is_visible_to_pro(self, client: TestClient) -> None:
        """THE DEFECT. Tap Sab band; Pro must not still say ACTIVE."""
        assert _state(client) == "ACTIVE"

        r = client.post(SIMPLE_TRIP)
        assert r.status_code == 200, r.text

        assert _state(client) == "TRIPPED"

    def test_pro_trip_is_visible_to_simple(self, client: TestClient) -> None:
        """The reverse. Simple's strip reads this same status endpoint, so a
        trip from Pro must show there too."""
        assert _state(client) == "ACTIVE"

        r = client.post(PRO_TRIP, json={"confirmation_token": _token(client)})
        assert r.status_code == 200, r.text

        assert _state(client) == "TRIPPED"

    def test_one_reset_clears_both(self, client: TestClient) -> None:
        """Reset once, and BOTH surfaces are clear — not one of them."""
        client.post(SIMPLE_TRIP)
        assert _state(client) == "TRIPPED"

        r = _reset(client)
        assert r.status_code == 200, r.text
        assert _state(client) == "ACTIVE"

        # and the brake still works afterwards
        client.post(SIMPLE_TRIP)
        assert _state(client) == "TRIPPED"

    @pytest.mark.asyncio
    async def test_trip_is_recorded_once(
        self, client: TestClient, maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """Idempotent: two taps on one brake is one event, not two.

        The endpoint's docstring has always promised idempotency; adding the
        gate must not quietly break it.
        """
        client.post(SIMPLE_TRIP)
        client.post(SIMPLE_TRIP)

        async with maker() as s:
            rows = (await s.execute(select(KillSwitchEvent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].reason == "manual"

    def test_still_reports_what_it_closed(self, client: TestClient) -> None:
        """The response contract is unchanged — Simple still reads these."""
        body = client.post(SIMPLE_TRIP).json()
        assert body["positions_closed"] == 0
        assert body["signals_rejected"] == 0
        assert "position" in body["message"]

    def test_does_not_reach_into_the_broker(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sab band is ONE UNCONFIRMED TAP.

        Pro's /kill-switch/trip gates the broker-level emergency square-off
        behind a confirmation token, because that chain once wiped personal
        Dhan positions alongside system ones. This endpoint must flip the gate
        and stop what the engine owns — and stop there. If someone later wires
        the square-off chain in here, this test fails and they have to argue
        for it in review.
        """
        from app.services import kill_switch_service as kss

        called: list[str] = []

        async def _boom(*a: Any, **kw: Any) -> Any:
            called.append("square_off")
            return [], []

        monkeypatch.setattr(
            kss.kill_switch_service,
            "_execute_emergency_square_off",
            _boom,
            raising=False,
        )
        assert client.post(SIMPLE_TRIP).status_code == 200
        assert called == [], "Sab band must not fire the broker square-off chain"
