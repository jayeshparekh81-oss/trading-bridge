"""FAN-OUT Module B+ — PIECE 0: MANUAL entry fix (founder-confirmed).

The AUTO/MANUAL mode-check must gate ENTRY dispatch too (it was exit-only).
A MANUAL (non-``auto``) subscriber → notify-only on entry, NO position opened
until the sub acts. AUTO → mirror position as before. Broker never called.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.services.marketplace_fanout import dispatch_subscriber_executions
from tests.integration.test_marketplace_fanout_webhook import (
    _run,
    _seed_listing_and_subs,
)


async def _mk_entry(maker, seed, *, symbol="NIFTY"):
    async with maker() as s:
        sig = StrategySignal(
            id=uuid.uuid4(), user_id=seed["user_id"],
            strategy_id=seed["strategy_id"], symbol=symbol, action="ENTRY",
            quantity=1, order_type="market", status="executed",
            raw_payload={"action": "ENTRY", "side": "long", "symbol": symbol,
                         "price": 100.0},
            received_at=datetime.now(UTC))
        s.add(sig)
        await s.commit()
        return sig


async def _strategy(maker, seed) -> Strategy:
    async with maker() as s:
        return await s.get(Strategy, seed["strategy_id"])


def _sub_rows(maker, strategy_id):
    async def _load():
        async with maker() as s:
            return list((await s.execute(select(StrategyPosition).where(
                StrategyPosition.strategy_id == strategy_id,
                StrategyPosition.subscription_id.is_not(None)))).scalars())

    return _run(_load())


def _manual(ref):
    return replace(ref, execution_mode="offline")   # offline = MANUAL (CHECK vocab)


def _auto(ref):
    return replace(ref, execution_mode="auto")


@pytest.fixture
def broker_spy(monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    return spy


def test_manual_entry_notify_only_auto_mirrors(
    client, seed, db_session_maker, broker_spy
):
    """MANUAL (offline) sub → notify_only, ZERO position. AUTO sub → mirror."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=2, n_cancelled=0,
        lots_overrides=[2, 2]))
    manual, auto = _manual(refs[0]), _auto(refs[1])
    sig = _run(_mk_entry(db_session_maker, seed))

    async def _go():
        async with db_session_maker() as s:
            return await dispatch_subscriber_executions(
                signal=sig, strategy=strat, subscribers=[manual, auto], db=s,
                signal_hash=f"H-{uuid.uuid4().hex}")

    by = {r.subscription_id: r for r in _run(_go())}

    # MANUAL — notify_only, message present, NO fill, NO position.
    m = by[manual.subscription_id]
    assert m.status == "notify_only"
    assert m.position_id is None and m.broker_order_id is None
    assert m.notify_message and "manual" in m.notify_message.lower()

    # AUTO — mirror position created.
    a = by[auto.subscription_id]
    assert a.status == "filled"
    assert a.position_id is not None
    assert a.quantity == 2

    # exactly ONE subscriber position row — the AUTO one, NOT the MANUAL one.
    rows = _sub_rows(db_session_maker, seed["strategy_id"])
    assert len(rows) == 1
    assert rows[0].subscription_id == auto.subscription_id
    broker_spy.assert_not_called()


def test_manual_entry_idempotent(
    client, seed, db_session_maker, broker_spy, monkeypatch, fake_redis
):
    """A re-delivered MANUAL entry (same signal_hash) → duplicate, not re-notify."""
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0,
        lots_overrides=[2]))
    manual = _manual(refs[0])
    sig = _run(_mk_entry(db_session_maker, seed))
    h = f"H-{uuid.uuid4().hex}"

    async def _go():
        async with db_session_maker() as s:
            return await dispatch_subscriber_executions(
                signal=sig, strategy=strat, subscribers=[manual], db=s,
                signal_hash=h)

    first = _run(_go())
    second = _run(_go())
    assert first[0].status == "notify_only"
    assert second[0].status == "duplicate"
    assert _sub_rows(db_session_maker, seed["strategy_id"]) == []
    broker_spy.assert_not_called()
