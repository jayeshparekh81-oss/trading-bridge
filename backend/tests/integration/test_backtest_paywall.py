"""Phase 2 Billing B3.3 — backtest premium-field gating.

The backtest endpoint is NEVER 402-gated (basic backtest is free). Instead,
when the paywall is enforced and the caller is not entitled, ONLY the premium
analytics sections are nulled AFTER computation; the basic result (incl. the
equity curve), version manifest, candles source and data-quality warnings stay
fully intact and free.

    premium (nulled when not entitled): reliability, health_card, truth,
        regime, deviation, trade_quality, diagnosis
    basic (always free):                backtest (+ equityCurve),
        version_manifest, candles_source, data_quality_warnings

Runs the REAL backtest pipeline against the synthetic-candle fallback (no
network), same harness as test_real_data_backtest. Flag OFF ⇒ behavior-neutral.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.strategy_engine.api.backtest as bt
from app.api.deps import get_current_active_user
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api import router as strategy_crud_router
from app.strategy_engine.api.backtest import router as strategy_backtest_router

_FUTURE = datetime(2099, 1, 1, tzinfo=UTC)
_PREMIUM_SECTIONS = [
    "reliability",
    "health_card",
    "truth",
    "regime",
    "deviation",
    "trade_quality",
    "diagnosis",
]

_SAMPLE_STRATEGY_JSON: dict[str, Any] = {
    "id": "b33_paywall_test",
    "name": "B3.3 paywall test",
    "mode": "expert",
    "indicators": [{"id": "ema_5", "type": "ema", "params": {"period": 5}}],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [{"type": "indicator", "left": "ema_5", "op": ">", "value": 95.0}],
    },
    "exit": {"targetPercent": 1.5, "stopLossPercent": 1.0},
    "risk": {},
    "execution": {"mode": "backtest", "orderType": "MARKET", "productType": "INTRADAY"},
}


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-btpw-{uuid.uuid4().hex}"
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


@pytest.fixture(autouse=True)
def _market_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the market gate OPEN → synthetic candle path (no network)."""

    async def _open() -> bool:
        return True

    monkeypatch.setattr("app.strategy_engine.api.backtest._market_is_open", _open)


def _set_paywall(monkeypatch: pytest.MonkeyPatch, *, on: bool) -> None:
    monkeypatch.setattr(bt, "get_settings", lambda: SimpleNamespace(paywall_enforced=on))


async def _seed_user(maker: async_sessionmaker[AsyncSession], *, plan_status: str) -> User:
    async with maker() as s:
        user = User(
            email=f"btpw-{uuid.uuid4().hex[:8]}@x",
            password_hash="x",
            is_active=True,
            plan_status=plan_status,
            plan_expires_at=_FUTURE if plan_status == "active" else None,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


async def _seed_strategy(
    maker: async_sessionmaker[AsyncSession], *, user_id: uuid.UUID
) -> Strategy:
    async with maker() as s:
        strategy = Strategy(
            user_id=user_id,
            name="B3.3 paywall backtest",
            strategy_json=dict(_SAMPLE_STRATEGY_JSON),
            is_active=True,
        )
        s.add(strategy)
        await s.commit()
        await s.refresh(strategy)
        return strategy


def _make_client(db_maker: async_sessionmaker[AsyncSession], user: User) -> TestClient:
    app = FastAPI()
    app.include_router(strategy_backtest_router)
    app.include_router(strategy_crud_router)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    async def _override_user() -> User:
        return user

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_active_user] = _override_user
    return TestClient(app)


async def _run_backtest(db_maker: async_sessionmaker[AsyncSession], user: User) -> dict[str, Any]:
    strategy = await _seed_strategy(db_maker, user_id=user.id)
    with _make_client(db_maker, user) as client:
        resp = client.post(f"/api/strategies/{strategy.id}/backtest", json={})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _assert_basic_intact(body: dict[str, Any]) -> None:
    """Basic result + equity curve + manifest stay free regardless of plan."""
    assert body["backtest"] is not None
    assert len(body["backtest"]["equityCurve"]) == 720  # synthetic fallback
    assert body["version_manifest"] is not None
    assert body["candles_source"] == "synthetic"


# ── 1. basic-backtest-stays-intact: none + flag ON ────────────────────


@pytest.mark.asyncio
async def test_basic_intact_premium_nulled_for_none_when_flag_on(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_paywall(monkeypatch, on=True)
    user = await _seed_user(db_maker, plan_status="none")
    body = await _run_backtest(db_maker, user)

    _assert_basic_intact(body)  # basic + equity curve fully intact
    for section in _PREMIUM_SECTIONS:
        assert body[section] is None, (section, body[section])
    # Explicit gating flag (B3.3 follow-up) — the signal B3.4 keys on.
    assert body["premium_gated"] is True


# ── 2. active + flag ON ⇒ all sections present ────────────────────────


@pytest.mark.asyncio
async def test_full_result_for_active_when_flag_on(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_paywall(monkeypatch, on=True)
    user = await _seed_user(db_maker, plan_status="active")
    body = await _run_backtest(db_maker, user)

    _assert_basic_intact(body)
    # The deterministically-populated premium sections of a successful
    # synthetic backtest must flow through for an entitled user.
    assert body["reliability"] is not None
    assert body["health_card"] is not None
    assert body["truth"] is not None
    assert body["regime"] is not None
    assert body["trade_quality"] is not None
    assert body["premium_gated"] is False


# ── 3. flag OFF ⇒ everyone (incl. none) gets all sections ─────────────


@pytest.mark.asyncio
async def test_full_result_for_none_when_flag_off(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_paywall(monkeypatch, on=False)
    user = await _seed_user(db_maker, plan_status="none")
    body = await _run_backtest(db_maker, user)

    _assert_basic_intact(body)
    # Behavior-neutral: a free user still gets the full premium payload.
    assert body["reliability"] is not None
    assert body["health_card"] is not None
    assert body["truth"] is not None
    assert body["regime"] is not None
    assert body["trade_quality"] is not None
    assert body["premium_gated"] is False
