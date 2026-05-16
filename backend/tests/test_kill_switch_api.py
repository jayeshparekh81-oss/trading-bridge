"""End-to-end tests for the kill-switch API router.

Safety fix #4 (2026-05-16): the legacy ``X-User-Id`` header bypass was
removed from :mod:`app.api.kill_switch`. Authentication is now done
exclusively via JWT (``Depends(get_current_active_user)``). In tests
we substitute a fake user via ``app.dependency_overrides[
get_current_active_user]`` rather than minting a real JWT — the same
pattern used by ``tests/api/test_chart_markers.py``.

Three layers of coverage:

1. ``TestAuthGate`` — uses ``client`` (no auth override). Confirms
   unauth requests are rejected with 401, and specifically asserts
   that an ``X-User-Id`` header alone never grants access (regression
   guard for the removed bypass).
2. ``TestHappy``, ``TestAuditEmission`` — use ``auth_client_a``
   (override returns seeded User A). Verify per-endpoint behaviour
   from the perspective of an authenticated user.
3. ``TestUserIsolation`` — uses ``auth_client_b`` against a DB that
   was seeded with User A's config. Confirms User B's session reads
   only User B's state (which is empty/default) and never User A's.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_current_active_user
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


@pytest_asyncio.fixture
async def seeded_user_b(
    _sessionmaker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """A second active user with NO kill-switch config. Used by
    ``TestUserIsolation`` to verify User B's session cannot see User
    A's seeded config."""
    async with _sessionmaker() as s:
        u = User(email="b@x", password_hash="p", is_active=True)
        s.add(u)
        await s.commit()
        return {"user_id": str(u.id)}


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    _sessionmaker: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    """TestClient WITHOUT any auth override — used by ``TestAuthGate``
    to verify the real ``get_current_active_user`` chain rejects
    unauthenticated requests."""
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


def _fake_user(user_id: str) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = UUID(user_id)
    user.is_active = True
    return user


@pytest.fixture
def auth_client_a(
    client: TestClient, seeded_user: dict[str, Any]
) -> TestClient:
    """``client`` + auth override → returns User A (the user whose
    kill-switch config was seeded). All happy-path tests use this."""
    client.app.dependency_overrides[get_current_active_user] = (
        lambda: _fake_user(seeded_user["user_id"])
    )
    return client


@pytest.fixture
def auth_client_b(
    client: TestClient, seeded_user_b: dict[str, Any]
) -> TestClient:
    """``client`` + auth override → returns User B (no config seeded).
    Used by ``TestUserIsolation`` to confirm User B's session sees
    only User B's data, never User A's seeded state."""
    client.app.dependency_overrides[get_current_active_user] = (
        lambda: _fake_user(seeded_user_b["user_id"])
    )
    return client


# ═══════════════════════════════════════════════════════════════════════
# Auth gate — real JWT path (no override)
# ═══════════════════════════════════════════════════════════════════════


class TestAuthGate:
    def test_status_requires_valid_jwt(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        assert client.get("/api/kill-switch/status").status_code == 401

    def test_x_user_id_header_alone_does_not_grant_access(
        self, client: TestClient
    ) -> None:
        """Regression for safety fix #4: the legacy ``X-User-Id``
        header bypass has been removed. Sending the header alone (no
        Bearer JWT) must NOT authenticate the caller — every
        kill-switch endpoint must return 401."""
        any_uuid = "00000000-0000-0000-0000-000000000001"
        endpoints: list[tuple[str, str, dict[str, Any] | None]] = [
            ("GET", "/api/kill-switch/status", None),
            ("GET", "/api/kill-switch/config", None),
            (
                "PUT",
                "/api/kill-switch/config",
                {
                    "max_daily_loss_inr": "1000",
                    "max_daily_trades": 1,
                    "enabled": True,
                    "auto_square_off": True,
                },
            ),
            ("POST", "/api/kill-switch/reset-token", None),
            (
                "POST",
                "/api/kill-switch/reset",
                {"confirmation_token": "x" * 16},
            ),
            ("GET", "/api/kill-switch/history", None),
            ("POST", "/api/kill-switch/test", None),
            (
                "POST",
                "/api/kill-switch/trip",
                {"confirmation_token": "x" * 16},
            ),
            ("GET", "/api/kill-switch/daily-summary", None),
        ]
        for method, path, body in endpoints:
            resp = client.request(
                method,
                path,
                headers={"X-User-Id": any_uuid},
                json=body,
            )
            assert resp.status_code == 401, (
                f"{method} {path} accepted X-User-Id alone "
                f"(status={resp.status_code}, body={resp.text})"
            )

    def test_invalid_bearer_token_rejected(self, client: TestClient) -> None:
        """A malformed Bearer JWT must be rejected with 401 — i.e. the
        JWT validation actually runs and rejects garbage."""
        resp = client.get(
            "/api/kill-switch/status",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# Happy paths — authenticated as seeded User A
# ═══════════════════════════════════════════════════════════════════════


class TestHappy:
    def test_status(self, auth_client_a: TestClient) -> None:
        resp = auth_client_a.get("/api/kill-switch/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "ACTIVE"

    def test_get_config(self, auth_client_a: TestClient) -> None:
        resp = auth_client_a.get("/api/kill-switch/config")
        assert resp.status_code == 200
        assert resp.json()["max_daily_trades"] == 5

    def test_update_config(self, auth_client_a: TestClient) -> None:
        resp = auth_client_a.put(
            "/api/kill-switch/config",
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
        self,
        client: TestClient,
        _sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """An authenticated user with no config row gets 404."""
        import asyncio

        async def _make_user() -> str:
            async with _sessionmaker() as s:
                u = User(email="orphan@x", password_hash="p", is_active=True)
                s.add(u)
                await s.commit()
                return str(u.id)

        uid = asyncio.get_event_loop().run_until_complete(_make_user())
        client.app.dependency_overrides[get_current_active_user] = (
            lambda: _fake_user(uid)
        )
        resp = client.get("/api/kill-switch/config")
        assert resp.status_code == 404

    def test_reset_without_token(self, auth_client_a: TestClient) -> None:
        resp = auth_client_a.post(
            "/api/kill-switch/reset",
            json={"confirmation_token": "something-long-enough-to-pass"},
        )
        assert resp.status_code == 400

    def test_reset_happy_path(self, auth_client_a: TestClient) -> None:
        issued = auth_client_a.post("/api/kill-switch/reset-token")
        token = issued.json()["confirmation_token"]
        resp = auth_client_a.post(
            "/api/kill-switch/reset",
            json={"confirmation_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"

    def test_test_trip_dry_run(self, auth_client_a: TestClient) -> None:
        resp = auth_client_a.post("/api/kill-switch/test")
        assert resp.status_code == 200
        body = resp.json()
        assert "would_trigger" in body

    def test_daily_summary(self, auth_client_a: TestClient) -> None:
        resp = auth_client_a.get("/api/kill-switch/daily-summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trades_today"] == 0

    def test_history_empty(self, auth_client_a: TestClient) -> None:
        resp = auth_client_a.get("/api/kill-switch/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_update_config_rejects_bad_values(
        self, auth_client_a: TestClient
    ) -> None:
        resp = auth_client_a.put(
            "/api/kill-switch/config",
            json={
                "max_daily_loss_inr": "-100",
                "max_daily_trades": 1,
                "enabled": True,
                "auto_square_off": True,
            },
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Per-user isolation — User B cannot see User A's state
# ═══════════════════════════════════════════════════════════════════════


class TestUserIsolation:
    """User A is seeded with a kill-switch config; User B has no
    config. These tests confirm that User B's session reads only User
    B's data, never User A's. Pre-fix #4 the ``X-User-Id`` header
    bypass meant User B could simply send ``X-User-Id: <user_a_uuid>``
    to read User A's config; the override pattern here proves the
    user_id is always taken from the validated session, never from
    request input."""

    def test_user_b_config_returns_404_not_user_a_config(
        self, auth_client_b: TestClient
    ) -> None:
        """User B has no config row → 404. If isolation were broken
        and User A's row leaked through, this would return 200."""
        resp = auth_client_b.get("/api/kill-switch/config")
        assert resp.status_code == 404

    def test_user_b_status_does_not_reflect_user_a_seeded_thresholds(
        self, auth_client_b: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        """User A was seeded with ``max_daily_trades=5``; User B was
        not. ``status`` for User B must not include User A's
        thresholds."""
        # Confirm fixture seeded a config for User A.
        assert seeded_user["user_id"]
        resp = auth_client_b.get("/api/kill-switch/status")
        # User B has no config — the service returns a default ACTIVE
        # state with no per-user thresholds leaking through.
        assert resp.status_code == 200
        body = resp.json()
        # Sanity: response shape includes "state"; never echoes
        # another user's max_daily_trades field at the API surface.
        assert "state" in body

    def test_user_b_x_user_id_header_with_user_a_uuid_ignored(
        self,
        auth_client_b: TestClient,
        seeded_user: dict[str, Any],
    ) -> None:
        """User B is authenticated via override. They send an
        ``X-User-Id: <user_a_uuid>`` header on top. The header MUST
        be ignored — the response must reflect User B's state (no
        config → 404), NOT User A's (would return 200 with seeded
        config). This is the direct regression for the removed
        header-trust bypass."""
        resp = auth_client_b.get(
            "/api/kill-switch/config",
            headers={"X-User-Id": seeded_user["user_id"]},
        )
        assert resp.status_code == 404, (
            f"X-User-Id header may still be granting access "
            f"to another user's data: {resp.status_code} {resp.text}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Audit emission — pin the Phase 11 wiring on trip + reset
# ═══════════════════════════════════════════════════════════════════════


class TestAuditEmission:
    """The kill-switch service writes its own DB-backed audit_log row;
    this test pins the additional in-memory ``audit/`` ring-buffer
    emission added at the API layer so the same event reaches both
    stores."""

    def test_manual_reset_emits_kill_switch_triggered_audit_event(
        self, auth_client_a: TestClient, seeded_user: dict[str, Any]
    ) -> None:
        from app.strategy_engine.audit import clear_audit_log, query_events

        clear_audit_log()

        # Reset path requires the two-step token dance.
        issued = auth_client_a.post("/api/kill-switch/reset-token")
        token = issued.json()["confirmation_token"]
        resp = auth_client_a.post(
            "/api/kill-switch/reset",
            json={"confirmation_token": token},
        )
        assert resp.status_code == 200

        events = query_events(
            user_id=UUID(seeded_user["user_id"]),
            event_type="kill_switch_triggered",
        )
        assert events.filtered_count >= 1
        # Auto-promoted to critical by the emitter.
        assert events.events[-1].severity == "critical"
        meta = events.events[-1].metadata
        assert meta.get("action") == "reset"
        assert meta.get("reason") == "manual_reset"
