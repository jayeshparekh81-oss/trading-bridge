"""End-to-end paper-mode test for ``POST /api/webhook/strategy/{token}``.

Drives the full strategy pipeline with the broker network call short-
circuited by ``strategy_paper_mode=True``:

    HMAC-signed POST  →  webhook receiver
                      →  StrategySignal row (status=received)
                      →  background AI validator (bypassed by
                         strategy.ai_validation_enabled=False)
                      →  strategy_executor in paper mode
                      →  StrategyExecution + StrategyPosition rows
                      →  signal.status='executed', broker_order_id='PAPER-…'

Stack: aiosqlite in-memory DB, fakeredis for the kill-switch & cache,
real Pydantic + real ``app.main.create_app()``. No broker SDK is hit
because the executor's paper branch never touches it.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import encrypt_credential, generate_webhook_token
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.models.webhook_token import WebhookToken
from app.db.session import get_session
from app.main import create_app
from app.schemas.broker import BrokerName

HMAC_HEADER = "X-Signature"
HMAC_SECRET = "paper-test-hmac-secret-1234567890"


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — DB, fake Redis, signed-in TestClient
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fresh in-memory DB shared by request session + helper writes."""
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


@pytest_asyncio.fixture
async def seed(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """User + Dhan credential + webhook token + paper-mode strategy.

    Mirrors the schema the production seed script writes against
    Postgres so live testing follows the same shape.
    """
    token_plain = generate_webhook_token()
    token_hash = hashlib.sha256(token_plain.encode("utf-8")).hexdigest()

    async with db_session_maker() as s:
        user = User(
            email="paper-e2e@tradetri.com",
            password_hash="x",
            is_active=True,
        )
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
            label="strategy-paper-test",
            is_active=True,
        )
        s.add(webhook)
        await s.flush()

        strategy = Strategy(
            user_id=user.id,
            name="paper-e2e-strategy",
            webhook_token_id=webhook.id,
            broker_credential_id=cred.id,
            entry_lots=1,
            partial_profit_lots=0,
            trail_lots=0,
            allowed_symbols=["NIFTY", "BSE1!", "BANKNIFTY"],
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


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> Iterator[TestClient]:
    """Wire the FastAPI app: paper mode forced ON, fake Redis, sqlite session."""
    # ── Force paper mode regardless of host .env ─────────────────────
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    from app.core import config as _config

    _config.get_settings.cache_clear()

    # ── Redis: singleton + lifespan path ─────────────────────────────
    async def _noop_close() -> None:
        return None

    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.core.redis_client.close_redis", _noop_close)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

    # ── DB engine: stub the lifespan engine so startup doesn't try
    # to reach Postgres. The per-request session is overridden below.
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

    # The strategy executor opens its own session in the background task;
    # point its sessionmaker at the same in-memory DB so the test reads
    # what the executor wrote.
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
    """Native TRADETRI payload — the strategy receiver's primary shape."""
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


def _wait_for_executed(
    db_session_maker: async_sessionmaker[AsyncSession],
    signal_id: uuid.UUID,
    *,
    timeout_s: float = 5.0,
) -> StrategySignal:
    """Poll until the signal reaches a terminal status.

    FastAPI's TestClient runs ``BackgroundTasks`` synchronously after
    the response, so this should resolve on the first iteration. The
    loop is defence-in-depth for slow CI machines.
    """
    deadline = time.perf_counter() + timeout_s

    async def _poll() -> StrategySignal:
        while True:
            async with db_session_maker() as s:
                row = await s.get(StrategySignal, signal_id)
                if row is not None and row.status in {
                    "executed",
                    "rejected",
                    "failed",
                }:
                    return row
            if time.perf_counter() > deadline:
                async with db_session_maker() as s:
                    last = await s.get(StrategySignal, signal_id)
                raise AssertionError(
                    f"signal {signal_id} did not reach terminal status in "
                    f"{timeout_s}s — last status: "
                    f"{last.status if last else 'missing'}"
                )
            await asyncio.sleep(0.05)

    return asyncio.get_event_loop().run_until_complete(_poll())


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestHappyPath:
    def test_paper_buy_flows_to_executed_position(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        body = _payload(action="BUY", quantity=1)
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["queued_for_processing"] is True
        signal_id = uuid.UUID(data["signal_id"])

        sig = _wait_for_executed(db_session_maker, signal_id)
        assert sig.status == "executed", f"notes={sig.notes!r}"

        async def _fetch_position() -> StrategyPosition | None:
            async with db_session_maker() as s:
                stmt = select(StrategyPosition).where(
                    StrategyPosition.signal_id == signal_id
                )
                return (await s.execute(stmt)).scalar_one_or_none()

        position = asyncio.get_event_loop().run_until_complete(_fetch_position())
        assert position is not None, "executor must open a strategy_position"
        assert position.status == "open"
        assert position.total_quantity == 1
        assert position.remaining_quantity == 1


class TestSignature:
    def test_invalid_signature_returns_401(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={HMAC_HEADER: "deadbeef", "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_missing_signature_returns_401(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload()
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401


class TestQuantityCeiling:
    def test_quantity_above_ceiling_rejected_400(
        self, client: TestClient, seed: dict[str, Any]
    ) -> None:
        body = _payload(quantity=99)
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400
        assert "ceiling" in resp.json()["detail"].lower()


class TestUnknownToken:
    def test_unknown_token_returns_404(self, client: TestClient) -> None:
        bogus = generate_webhook_token()
        body = _payload()
        resp = client.post(
            _url(bogus),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 404


class TestPaperOrderId:
    def test_broker_order_id_starts_with_PAPER(
        self,
        client: TestClient,
        seed: dict[str, Any],
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Paper fills mark themselves with a ``PAPER-`` prefix.

        The strategy_executor mints ``PAPER-{uuid}`` whenever
        ``settings.strategy_paper_mode`` is True. Asserting on the
        prefix is what guarantees no real broker call slipped through.
        """
        body = _payload(quantity=1)
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 202
        signal_id = uuid.UUID(resp.json()["signal_id"])
        sig = _wait_for_executed(db_session_maker, signal_id)
        assert sig.status == "executed"

        async def _fetch_position() -> StrategyPosition | None:
            async with db_session_maker() as s:
                stmt = select(StrategyPosition).where(
                    StrategyPosition.signal_id == signal_id
                )
                return (await s.execute(stmt)).scalar_one_or_none()

        pos = asyncio.get_event_loop().run_until_complete(_fetch_position())
        assert pos is not None
        # The broker_order_id is on strategy_executions (one row per leg);
        # fetch via signal to keep the assertion broker-agnostic.
        async def _fetch_executions() -> list[Any]:
            from app.db.models.strategy_execution import StrategyExecution

            async with db_session_maker() as s:
                stmt = select(StrategyExecution).where(
                    StrategyExecution.signal_id == signal_id
                )
                return list((await s.execute(stmt)).scalars().all())

        executions = asyncio.get_event_loop().run_until_complete(
            _fetch_executions()
        )
        assert executions, "executor must persist a strategy_executions row"
        for ex in executions:
            assert ex.broker_order_id.startswith("PAPER-"), ex.broker_order_id
