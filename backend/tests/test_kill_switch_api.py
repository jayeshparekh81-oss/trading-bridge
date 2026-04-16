"""End-to-end tests for the kill-switch API router."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core import redis_client
from app.db.base import Base
from app.db.models.kill_switch import KillSwitchConfig
from app.db.models.user import User
from app.db.session import get_session


@pytest_asyncio.fixture
async def _sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_user(
    _sessionmaker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    async with _sessionmaker() as s:
        u = User(email="t@x", password_hash="p", is_active=True)
        s.add(u)
        await s.flush()
        s.add(
            KillSwitchConfig(
                user_id=u.id,
                max_daily_loss_inr=Decimal("1000"),
                max_daily_trades=5,
                enabled=True,
                auto_square_off=True,
            )
        )
        await s.commit()
        return {"user_id": str(u.id)}


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    _sessionmaker: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    fake_redis = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake_redis)

    async def _noop() -> None:
        return None

    class _Engine:
        async def dispose(self) -> None:
            return None

        def connect(self) -> Any:
            class _C:
                async def execute(self, *a: Any, **kw: Any) -> Any:
                    return MagicMock()

                async def __aenter__(self) -> Any:
                    return self

                async def __aexit__(self, *a: Any) -> None:
                    return None

            return _C()

    monkeypatch.setattr("app.db.session.get_engine", lambda: _Engine())
    monkeypatch.setattr(
        "app.db.session.dispose_engine", AsyncMock(return_value=None)
    )
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: MagicMock(
        ping=AsyncMock(return_value=True), aclose=AsyncMock(return_value=None)
    ))

    from app.main import create_app

    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with _sessionmaker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════
# Auth gate
# ═══════════════════════════════════════════════════════════════════════


class TestAuthGate:
    def test_status_requires_header(self, client: TestClient) -> None:
        assert client.get("/api/kill-switch/status").status_code == 401

    def test_bad_uuid_rejected(self, client: TestClient) -> None:
        assert (
            client.get(
                "/api/kill-switch/status", headers={"X-User-Id": "not-a-uuid"}
            ).status_code
            == 401
        )


# ═══════════════════════════════════════════════════════════════════════
# Happy paths
# ═══════════════════════════════════════════════════════════════════════


class TestHappy:
    def test_status(self, client: TestClient, seeded_user: dict[str, Any]) -> None:
        resp = client.get(
            "/api/kill-switch/status",
            headers={"X-User-Id": seeded_user["user_id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "ACTIVE"

    def test_get_config(self, client: TestClient, seeded_user: dict[str, Any]) -> None:
        resp = client.get(
            "/api/kill-switch/config",
            headers={"X-User-Id": seeded_user["user_id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["max_daily_trades"] == 5

    def test_update_config(
        self, client: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        resp = client.put(
            "/api/kill-switch/config",
            headers={"X-User-Id": seeded_user["user_id"]},
            json={
                "max_daily_loss_inr": "25000",
                "max_daily_trades": 50,
                "enabled": True,
                "auto_square_off": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["max_daily_trades"] == 50

    def test_config_404_when_missing(
        self, client: TestClient, _sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        import asyncio

        async def _make_user() -> str:
            async with _sessionmaker() as s:
                u = User(email="orphan@x", password_hash="p", is_active=True)
                s.add(u)
                await s.commit()
                return str(u.id)

        uid = asyncio.get_event_loop().run_until_complete(_make_user())
        resp = client.get(
            "/api/kill-switch/config", headers={"X-User-Id": uid}
        )
        assert resp.status_code == 404

    def test_reset_without_token(
        self, client: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        resp = client.post(
            "/api/kill-switch/reset",
            headers={"X-User-Id": seeded_user["user_id"]},
            json={"confirmation_token": "something-long-enough-to-pass"},
        )
        assert resp.status_code == 400

    def test_reset_happy_path(
        self, client: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        issued = client.post(
            "/api/kill-switch/reset-token",
            headers={"X-User-Id": seeded_user["user_id"]},
        )
        token = issued.json()["confirmation_token"]
        resp = client.post(
            "/api/kill-switch/reset",
            headers={"X-User-Id": seeded_user["user_id"]},
            json={"confirmation_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"

    def test_test_trip_dry_run(
        self, client: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        resp = client.post(
            "/api/kill-switch/test",
            headers={"X-User-Id": seeded_user["user_id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "would_trigger" in body

    def test_daily_summary(
        self, client: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        resp = client.get(
            "/api/kill-switch/daily-summary",
            headers={"X-User-Id": seeded_user["user_id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["trades_today"] == 0

    def test_history_empty(
        self, client: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        resp = client.get(
            "/api/kill-switch/history",
            headers={"X-User-Id": seeded_user["user_id"]},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_update_config_rejects_bad_values(
        self, client: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        resp = client.put(
            "/api/kill-switch/config",
            headers={"X-User-Id": seeded_user["user_id"]},
            json={
                "max_daily_loss_inr": "-100",
                "max_daily_trades": 1,
                "enabled": True,
                "auto_square_off": True,
            },
        )
        assert resp.status_code == 422
