"""Idempotency tests for ``POST /api/webhook/strategy/{token}``.

Mirrors the pattern proven by :mod:`test_strategy_webhook_paper_e2e`:
aiosqlite in-memory DB, fakeredis for the cache & idempotency claim,
real ``app.main.create_app()``. The strategy executor's paper branch
runs synchronously after the response so each POST settles fully
before the assertions fire.

Coverage targets:

* Duplicate within the Redis window → 200 ``status="duplicate"``,
  no second :class:`StrategySignal` row.
* Same body, distinct ``signal_id`` field → both succeed.
* Same body, Redis flushed mid-window → both succeed (documented
  limitation: idempotency is best-effort and bound by Redis durability).
* Same body from two different users → both succeed (key is
  prefixed with ``user_id``).
* Direct unit assertion on :func:`_compute_strategy_signal_hash` to
  pin both branches (signal_id present vs. absent).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.strategy_webhook import _compute_strategy_signal_hash
from app.core.security import encrypt_credential, generate_webhook_token
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.models.webhook_token import WebhookToken
from app.db.session import get_session
from app.main import create_app
from app.schemas.broker import BrokerName

HMAC_HEADER = "X-Signature"
HMAC_SECRET = "idempotency-test-hmac-secret-1234567890"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — DB, fake Redis, signed-in TestClient
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fake_aioredis.FakeRedis]:
    c = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield c
    finally:
        await c.aclose()


async def _seed_user_with_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
) -> dict[str, Any]:
    """Create one user + Dhan creds + token + active paper-mode strategy."""
    token_plain = generate_webhook_token()
    token_hash = hashlib.sha256(token_plain.encode("utf-8")).hexdigest()

    async with maker() as s:
        user = User(email=email, password_hash="x", is_active=True)
        s.add(user)
        await s.flush()

        cred = BrokerCredential(
            user_id=user.id,
            broker_name=BrokerName.DHAN,
            client_id_enc=encrypt_credential("DHAN-CID"),
            api_key_enc=encrypt_credential("DHAN-KEY"),
            api_secret_enc=encrypt_credential("DHAN-SECRET"),
            access_token_enc=encrypt_credential("DHAN-TOK"),
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            is_active=True,
        )
        s.add(cred)
        await s.flush()

        webhook = WebhookToken(
            user_id=user.id,
            token_hash=token_hash,
            hmac_secret_enc=encrypt_credential(HMAC_SECRET),
            label=f"idem-test-{email}",
            is_active=True,
        )
        s.add(webhook)
        await s.flush()

        strategy = Strategy(
            user_id=user.id,
            name=f"idem-strategy-{email}",
            webhook_token_id=webhook.id,
            broker_credential_id=cred.id,
            entry_lots=1,
            partial_profit_lots=0,
            trail_lots=0,
            allowed_symbols=["NIFTY", "BANKNIFTY"],
            ai_validation_enabled=False,
            is_active=True,
        )
        s.add(strategy)
        await s.commit()

        return {
            "token_plain": token_plain,
            "user_id": user.id,
            "credential_id": cred.id,
            "webhook_id": webhook.id,
            "strategy_id": strategy.id,
        }


@pytest_asyncio.fixture
async def seed(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    return await _seed_user_with_strategy(db_session_maker, email="idem@tradetri.com")


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> Iterator[TestClient]:
    """Wire the FastAPI app — paper mode ON, fake Redis, sqlite session."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    from app.core import config as _config

    _config.get_settings.cache_clear()

    async def _noop_close() -> None:
        return None

    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.core.redis_client.close_redis", _noop_close)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

    class _FakeEngine:
        async def dispose(self) -> None:
            return None

        def connect(self) -> Any:
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def _ctx() -> Any:
                conn = MagicMock()
                conn.execute = AsyncMock(return_value=MagicMock())
                yield conn

            return _ctx()

    monkeypatch.setattr("app.db.session.get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(
        "app.db.session.dispose_engine", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "app.db.session.get_sessionmaker", lambda: db_session_maker
    )

    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _sign(body: bytes, secret: str = HMAC_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _payload(**overrides: Any) -> bytes:
    base: dict[str, Any] = {
        "action": "BUY",
        "symbol": "NIFTY",
        "quantity": 1,
        "order_type": "market",
        "price": 22500.0,
    }
    base.update(overrides)
    return json.dumps(base).encode("utf-8")


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


async def _count_signals(
    maker: async_sessionmaker[AsyncSession], user_id: UUID
) -> int:
    async with maker() as s:
        stmt = select(func.count(StrategySignal.id)).where(
            StrategySignal.user_id == user_id
        )
        return int((await s.execute(stmt)).scalar_one())


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDuplicateSuppression:
    def test_identical_body_second_call_returns_200_duplicate(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Same body twice within the 60 s window → second is suppressed.

        Asserts the legacy-exact response shape: HTTP 200, JSON body
        ``{"status": "duplicate", "message": "duplicate signal suppressed"}``,
        and that no second :class:`StrategySignal` row was written.
        """
        body = _payload(action="BUY", quantity=1)
        headers = {
            HMAC_HEADER: _sign(body),
            "Content-Type": "application/json",
        }

        first = client.post(_url(seed["token_plain"]), content=body, headers=headers)
        second = client.post(_url(seed["token_plain"]), content=body, headers=headers)

        assert first.status_code == 202, first.text
        assert first.json()["status"] == "accepted"

        assert second.status_code == 200, second.text
        body_json = second.json()
        assert body_json == {
            "status": "duplicate",
            "message": "duplicate signal suppressed",
        }

        import asyncio

        count = asyncio.get_event_loop().run_until_complete(
            _count_signals(db_session_maker, seed["user_id"])
        )
        assert count == 1, "duplicate must not write a second StrategySignal row"


class TestDistinctSignalId:
    def test_same_body_with_different_signal_id_both_accepted(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """``signal_id`` is the explicit dedup key — two values, two signals."""
        body1 = _payload(signal_id="alpha-001")
        body2 = _payload(signal_id="alpha-002")

        r1 = client.post(
            _url(seed["token_plain"]),
            content=body1,
            headers={HMAC_HEADER: _sign(body1), "Content-Type": "application/json"},
        )
        r2 = client.post(
            _url(seed["token_plain"]),
            content=body2,
            headers={HMAC_HEADER: _sign(body2), "Content-Type": "application/json"},
        )

        assert r1.status_code == 202, r1.text
        assert r2.status_code == 202, r2.text
        assert r1.json()["signal_id"] != r2.json()["signal_id"]

        import asyncio

        count = asyncio.get_event_loop().run_until_complete(
            _count_signals(db_session_maker, seed["user_id"])
        )
        assert count == 2


class TestRedisFlushMidWindow:
    def test_redis_flush_between_calls_lets_duplicate_through(
        self,
        client: TestClient,
        seed: dict[str, Any],
        fake_redis: fake_aioredis.FakeRedis,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Documented limitation: idempotency is bound by Redis durability.

        If the Redis instance is flushed (or evicted, or fails over to a
        replica without the slot), a retry sent within the original 60 s
        window will be processed a second time. This is acceptable — the
        executor's deterministic-paper branch and the broker's own
        idempotency guard the actual order side. The test pins the
        behaviour so future contributors can't quietly tighten it without
        weighing the Redis-availability tradeoff.
        """
        body = _payload(quantity=1)
        headers = {
            HMAC_HEADER: _sign(body),
            "Content-Type": "application/json",
        }

        first = client.post(_url(seed["token_plain"]), content=body, headers=headers)
        assert first.status_code == 202, first.text

        import asyncio

        asyncio.get_event_loop().run_until_complete(fake_redis.flushall())

        second = client.post(_url(seed["token_plain"]), content=body, headers=headers)
        assert second.status_code == 202, second.text

        count = asyncio.get_event_loop().run_until_complete(
            _count_signals(db_session_maker, seed["user_id"])
        )
        assert count == 2, "post-flush retry must produce a fresh signal row"


class TestUserScoping:
    def test_same_body_from_two_users_both_accepted(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Idempotency keys are prefixed with ``user_id`` — no cross-user collision."""
        import asyncio

        seed_b = asyncio.get_event_loop().run_until_complete(
            _seed_user_with_strategy(db_session_maker, email="other@tradetri.com")
        )

        body = _payload(quantity=1)
        headers = {
            HMAC_HEADER: _sign(body),
            "Content-Type": "application/json",
        }

        ra = client.post(_url(seed["token_plain"]), content=body, headers=headers)
        rb = client.post(_url(seed_b["token_plain"]), content=body, headers=headers)

        assert ra.status_code == 202, ra.text
        assert rb.status_code == 202, rb.text

        count_a = asyncio.get_event_loop().run_until_complete(
            _count_signals(db_session_maker, seed["user_id"])
        )
        count_b = asyncio.get_event_loop().run_until_complete(
            _count_signals(db_session_maker, seed_b["user_id"])
        )
        assert count_a == 1
        assert count_b == 1


# ═══════════════════════════════════════════════════════════════════════
# Unit — pin both branches of _compute_strategy_signal_hash
# ═══════════════════════════════════════════════════════════════════════


class TestSignalHashFunction:
    def test_signal_id_branch(self) -> None:
        uid = uuid.uuid4()
        key = _compute_strategy_signal_hash(
            uid, {"signal_id": "abc-123", "action": "BUY"}, b"ignored"
        )
        assert key == f"{uid}:abc-123"

    def test_raw_body_fallback_branch(self) -> None:
        uid = uuid.uuid4()
        raw = b'{"action":"BUY","symbol":"NIFTY"}'
        key = _compute_strategy_signal_hash(uid, {"action": "BUY"}, raw)
        expected_digest = hashlib.sha256(raw).hexdigest()
        assert key == f"{uid}:{expected_digest}"

    def test_empty_signal_id_falls_back_to_body_hash(self) -> None:
        """``signal_id=""`` (falsy) must take the raw-body branch — no empty-key bug."""
        uid = uuid.uuid4()
        raw = b'{"action":"SELL"}'
        key = _compute_strategy_signal_hash(uid, {"signal_id": ""}, raw)
        assert key == f"{uid}:{hashlib.sha256(raw).hexdigest()}"
