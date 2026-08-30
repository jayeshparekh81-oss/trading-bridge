"""Subscriber drift pass — separate worker, default-OFF, places no orders."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_position import StrategyPosition
from app.workers.subscriber_drift_pass import run_subscriber_drift_pass


@dataclass
class FakeBrokerPos:
    symbol: str
    quantity: int


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tt-driftpass-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    # Only the tables this file touches: Base.metadata.create_all fails on
    # SQLite once a JSONB-bearing model is registered (strategy_templates
    # .config_json), which happens as soon as anything in the session imports
    # the marketplace router.
    _tables = [
        Base.metadata.tables[t]
        for t in ("users", "marketplace_subscriptions", "strategy_positions",
                  "audit_logs")
        if t in Base.metadata.tables
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=_tables)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest.fixture
def drift_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "subscriber_drift_enabled", True)


async def _seed(maker, *, execution_mode="auto", is_paper=False,
                symbol="BSE-AUG2026-FUT", qty=2, status="open"):
    async with maker() as s:
        strat = uuid.uuid4()
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(), subscriber_id=uuid.uuid4(),
            subscribed_at=datetime.now(UTC), status="active",
            amount_paid_inr=Decimal("0"),
            execution_mode=execution_mode, is_paper=is_paper,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        pos = StrategyPosition(
            strategy_id=strat, subscription_id=sub.id,
            user_id=sub.subscriber_id, symbol=symbol,
            side="buy", total_quantity=qty, remaining_quantity=qty,
            status=status, opened_at=datetime.now(UTC),
            broker_credential_id=uuid.uuid4(),
        )
        s.add(pos)
        await s.commit()
        return sub.id


async def _mode(maker, sub_id) -> str:
    async with maker() as s:
        row = (await s.execute(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.id == sub_id))).scalar_one()
        return row.execution_mode


def _fetch(positions):
    async def _f(_sid):
        return positions
    return _f


# ═══════════════════════════════════════════════════════════════════════
# Flag: default OFF
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_flag_defaults_off():
    assert get_settings().subscriber_drift_enabled is False


@pytest.mark.asyncio
async def test_dormant_when_flag_off_touches_nothing(db_maker):
    sub_id = await _seed(db_maker)
    called = False

    async def fetch(_sid):
        nonlocal called
        called = True
        return []

    async with db_maker() as db:
        report = await run_subscriber_drift_pass(db, fetch_broker_positions=fetch)

    assert report.dormant is True
    assert report.checked == 0
    assert called is False                      # no broker call at all
    assert await _mode(db_maker, sub_id) == "auto"


# ═══════════════════════════════════════════════════════════════════════
# Detection + flip
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_broker_flat_flips_to_manual(db_maker, drift_on):
    sub_id = await _seed(db_maker)
    async with db_maker() as db:
        report = await run_subscriber_drift_pass(
            db, fetch_broker_positions=_fetch([]))
    assert report.checked == 1
    assert report.flipped == 1
    assert await _mode(db_maker, sub_id) == "offline"


@pytest.mark.asyncio
async def test_broker_confirms_position_no_flip(db_maker, drift_on):
    """Compact broker spelling must match the canonical stored one."""
    sub_id = await _seed(db_maker)
    async with db_maker() as db:
        report = await run_subscriber_drift_pass(
            db, fetch_broker_positions=_fetch([FakeBrokerPos("BSE26AUGFUT", 2)]))
    assert report.flipped == 0
    assert await _mode(db_maker, sub_id) == "auto"


@pytest.mark.asyncio
async def test_partial_close_at_broker_flips(db_maker, drift_on):
    sub_id = await _seed(db_maker, qty=4)
    async with db_maker() as db:
        report = await run_subscriber_drift_pass(
            db, fetch_broker_positions=_fetch([FakeBrokerPos("BSE26AUGFUT", 2)]))
    assert report.flipped == 1
    assert await _mode(db_maker, sub_id) == "offline"


# ═══════════════════════════════════════════════════════════════════════
# Fail-safe
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_broker_unavailable_does_not_flip(db_maker, drift_on):
    async def boom(_sid):
        raise ConnectionError("down")

    sub_id = await _seed(db_maker)
    async with db_maker() as db:
        report = await run_subscriber_drift_pass(db, fetch_broker_positions=boom)
    assert report.flipped == 0
    assert report.unknown == 1
    assert await _mode(db_maker, sub_id) == "auto"


@pytest.mark.asyncio
async def test_ambiguous_symbol_does_not_flip(db_maker, drift_on):
    """A garbled broker symbol is not evidence of a close."""
    sub_id = await _seed(db_maker)
    async with db_maker() as db:
        report = await run_subscriber_drift_pass(
            db, fetch_broker_positions=_fetch([FakeBrokerPos("!!!GARBAGE", 2)]))
    assert report.flipped == 0
    assert await _mode(db_maker, sub_id) == "auto"


# ═══════════════════════════════════════════════════════════════════════
# Candidate scoping
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"execution_mode": "offline"}, "already manual"),
        ({"is_paper": True}, "paper — no broker position exists"),
        ({"status": "closed"}, "no open position"),
    ],
)
async def test_out_of_scope_subscriptions_are_not_checked(db_maker, drift_on, kwargs, why):
    await _seed(db_maker, **kwargs)
    async with db_maker() as db:
        report = await run_subscriber_drift_pass(
            db, fetch_broker_positions=_fetch([]))
    assert report.checked == 0, f"should not have checked: {why}"


# ═══════════════════════════════════════════════════════════════════════
# ⚠️ Places NOTHING
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_never_places_an_order(db_maker, drift_on, monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    await _seed(db_maker)
    async with db_maker() as db:
        await run_subscriber_drift_pass(db, fetch_broker_positions=_fetch([]))

    spy.assert_not_called()


def _code_only(mod) -> str:
    """Module source minus its docstring.

    The docstring legitimately *names* the things the module must not do (e.g.
    it explains that reconciliation_loop is untouched), so static guards must
    look at CODE, not prose.
    """
    import inspect

    src = inspect.getsource(mod)
    doc = mod.__doc__ or ""
    return src.replace(doc, "", 1) if doc else src


def test_module_places_no_orders_and_schedules_nothing():
    from app.workers import subscriber_drift_pass as mod

    code = _code_only(mod)
    for forbidden in ("place_order(", "square_off(", "beat_schedule",
                      "asyncio.create_task", "while True", "add_periodic_task"):
        assert forbidden not in code, f"drift pass must not contain {forbidden!r}"


def test_does_not_import_or_call_reconciliation_loop():
    """The live-money loop must stay completely independent of this worker."""
    from app.workers import subscriber_drift_pass as mod

    code = _code_only(mod)
    assert "from app.workers.reconciliation_loop" not in code
    assert "import reconciliation_loop" not in code
