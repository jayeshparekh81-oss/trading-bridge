"""DURABLE HALT STORE — ``RedisHaltStore`` (Module B+).

A Redis-backed :class:`HaltFlagStore` so the master-emergency halt flag survives
a process restart and is shared across the backend + worker (the in-process
store is per-process). Reuses the app's existing ``settings.redis_url`` (a SYNC
connection so it satisfies the SYNC HaltFlagStore interface — zero caller
changes). Fail-CLOSED: Redis unreachable → ``is_halted()`` returns True.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import fakeredis
from sqlalchemy import select

from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.services.kill_switch_service import KillSwitchService
from app.services.master_emergency import (
    RedisHaltStore,
    is_platform_halted,
)
from tests.integration.test_marketplace_fanout_webhook import (
    _make_position,
    _run,
    _seed_listing_and_subs,
)

# ═══════════════════════════════════════════════════════════════════════
# Pure store behaviour (no DB)
# ═══════════════════════════════════════════════════════════════════════


def test_redis_halt_store_set_get():
    fake = fakeredis.FakeRedis(decode_responses=True)
    store = RedisHaltStore(client=fake)
    assert store.is_halted() is False
    store.set_halted(True)
    assert store.is_halted() is True
    store.set_halted(False)
    assert store.is_halted() is False


def test_redis_halt_store_writes_reason_and_timestamp():
    fake = fakeredis.FakeRedis(decode_responses=True)
    store = RedisHaltStore(client=fake, reason="broker outage")
    store.set_halted(True)
    raw = fake.get("platform:emergency_halt")
    payload = json.loads(raw)
    assert payload["halted"] is True
    assert payload["reason"] == "broker outage"
    assert payload.get("at")


def test_redis_halt_store_cross_instance_durability():
    """The whole point: a SECOND store instance on a SEPARATE connection to the
    SAME Redis sees the halt → proves cross-process / restart survival."""
    server = fakeredis.FakeServer()
    c1 = fakeredis.FakeRedis(server=server, decode_responses=True)
    c2 = fakeredis.FakeRedis(server=server, decode_responses=True)

    RedisHaltStore(client=c1).set_halted(True)
    # A different connection (simulating another process / a restart) reads it.
    assert RedisHaltStore(client=c2).is_halted() is True
    assert is_platform_halted(store=RedisHaltStore(client=c2)) is True


def test_redis_halt_store_fails_closed_when_unreachable():
    """Redis down → is_halted() returns True (fail-CLOSED — a safety switch must
    block when it cannot confirm the platform is safe)."""
    broken = MagicMock(name="redis")
    broken.get.side_effect = ConnectionError("redis down")
    store = RedisHaltStore(client=broken)
    assert store.is_halted() is True                       # FAIL-CLOSED
    assert is_platform_halted(store=store) is True


def test_redis_halt_store_set_failure_is_swallowed():
    """A set failure is logged, not raised — it must not break the close-all in
    execute_master_emergency (the close is the critical safety action)."""
    broken = MagicMock(name="redis")
    broken.set.side_effect = ConnectionError("redis down")
    broken.delete.side_effect = ConnectionError("redis down")
    store = RedisHaltStore(client=broken)
    store.set_halted(True)                                  # must not raise
    store.set_halted(False)                                 # must not raise


# ═══════════════════════════════════════════════════════════════════════
# Durable path end-to-end: execute_master_emergency with a Redis store
# ═══════════════════════════════════════════════════════════════════════


async def _make_paper(maker, strategy_id):
    async with maker() as s:
        strat = await s.get(Strategy, strategy_id)
        strat.is_paper = True
        await s.commit()


def _owner_pos(maker, strategy_id):
    async def _load():
        async with maker() as s:
            return (await s.execute(select(StrategyPosition).where(
                StrategyPosition.strategy_id == strategy_id,
                StrategyPosition.subscription_id.is_(None)))).scalars().first()

    return _run(_load())


def test_execute_master_emergency_persists_halt_to_redis(
    client, seed, db_session_maker, monkeypatch
):
    """execute_master_emergency with an injected RedisHaltStore closes positions
    AND persists the halt durably — a second store (another connection) sees it."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "marketplace_fanout_enabled", True)
    from app.brokers.dhan import DhanBroker
    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)

    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=None))
    _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))

    server = fakeredis.FakeServer()
    store = RedisHaltStore(client=fakeredis.FakeRedis(server=server, decode_responses=True))

    async def _go():
        async with db_session_maker() as s:
            return await KillSwitchService().execute_master_emergency(
                s, "durable drill", halt_store=store)

    res = _run(_go())

    assert res["status"] == "halted" and res["closed"] == 1
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"
    # A DIFFERENT connection (another process / after restart) sees the halt.
    other = RedisHaltStore(client=fakeredis.FakeRedis(server=server, decode_responses=True))
    assert other.is_halted() is True
    assert is_platform_halted(store=other) is True
    spy.assert_not_called()
