"""KILL-SWITCH 3-TIER — TIER 3 (master emergency enforcement).

``KillSwitchService.execute_master_emergency(session, reason)`` wires the
already-built + tested ``master_emergency_halt`` PLAN into a real halt:
  * builds the plan + trips the halt flag (reuses master_emergency_halt as-is);
  * ACTUALLY closes every open position platform-wide (owner + subscribers,
    across all strategies) by reusing Tier-2 ``kill_strategy`` (→ close
    primitives + Tier-1 cascade);
  * ACTUALLY forces every active subscriber to MANUAL (execution_mode
    'offline') — a ROW UPDATE, not a migration;
  * exposes ``is_platform_halted()`` for the (deferred) webhook block.

Assumption (tested): master-emergency RESPECTS ``marketplace_fanout_enabled``
(dormant default) — it's the marketplace platform's halt, consistent with
Tier 1/2. PAPER stage: broker place_order NEVER invoked.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.services.kill_switch_service import KillSwitchService
from app.services.master_emergency import InProcessHaltStore, is_platform_halted
from tests.integration.test_marketplace_fanout_webhook import (
    _make_position,
    _run,
    _seed_listing_and_subs,
)


@pytest.fixture
def broker_spy(monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    return spy


@pytest.fixture
def fanout_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "marketplace_fanout_enabled", True)


async def _make_paper(maker, strategy_id):
    async with maker() as s:
        strat = await s.get(Strategy, strategy_id)
        strat.is_paper = True
        await s.commit()


async def _make_strategy_y(maker, seed, name="strategy-Y"):
    async with maker() as s:
        strat = Strategy(
            user_id=seed["user_id"], name=name,
            broker_credential_id=seed["credential_id"], is_paper=True,
            is_active=True)
        s.add(strat)
        await s.commit()
        return strat.id


def _owner_position(maker, seed, strategy_id=None):
    _run(_make_position(
        maker, user_id=seed["user_id"],
        strategy_id=strategy_id or seed["strategy_id"],
        credential_id=seed["credential_id"], symbol="NIFTY", side="buy",
        qty=2, subscription_id=None))


def _subs_with_positions(seed, maker, strategy_id=None, n=2):
    sid = strategy_id or seed["strategy_id"]
    refs = _run(_seed_listing_and_subs(
        maker, strategy_id=sid, creator_id=seed["user_id"], n_active=n,
        n_cancelled=0))
    for r in refs:
        _run(_make_position(
            maker, user_id=r.subscriber_id, strategy_id=sid,
            credential_id=seed["credential_id"], symbol="NIFTY", side="buy",
            qty=2, subscription_id=r.subscription_id))
    return refs


def _pos(maker, strategy_id, subscription_id):
    async def _load():
        async with maker() as s:
            return (await s.execute(select(StrategyPosition).where(
                StrategyPosition.strategy_id == strategy_id,
                StrategyPosition.subscription_id == subscription_id))).scalars().first()

    return _run(_load())


def _owner_pos(maker, strategy_id):
    async def _load():
        async with maker() as s:
            return (await s.execute(select(StrategyPosition).where(
                StrategyPosition.strategy_id == strategy_id,
                StrategyPosition.subscription_id.is_(None)))).scalars().first()

    return _run(_load())


def _active_sub_modes(maker):
    async def _load():
        async with maker() as s:
            return list((await s.execute(select(
                MarketplaceSubscription.execution_mode).where(
                MarketplaceSubscription.status == "active"))).scalars())

    return _run(_load())


def _master(maker, reason, store):
    async def _go():
        async with maker() as s:
            return await KillSwitchService().execute_master_emergency(
                s, reason, halt_store=store)

    return _run(_go())


# ═══════════════════════════════════════════════════════════════════════
# TIER 3 — master emergency enforcement
# ═══════════════════════════════════════════════════════════════════════


def test_master_emergency_closes_all_and_forces_manual(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    store = InProcessHaltStore()
    # Strategy X (seed) — owner + 2 subs.
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)
    x_subs = _subs_with_positions(seed, db_session_maker, n=2)
    # Strategy Y — owner + 1 sub (cross-strategy coverage).
    y_id = _run(_make_strategy_y(db_session_maker, seed))
    _owner_position(db_session_maker, seed, strategy_id=y_id)
    y_subs = _subs_with_positions(seed, db_session_maker, strategy_id=y_id, n=1)

    assert is_platform_halted(store=store) is False
    res = _master(db_session_maker, "broker outage", store)

    # halt flag tripped + audit present
    assert res["status"] == "halted"
    assert res["halted"] is True and is_platform_halted(store=store) is True
    assert res["audit_entry"]["event"] == "master_emergency_halt"
    assert res["closed"] == 5          # 2 owners + 3 subscriber positions

    # EVERY position closed — owners and all subs, both strategies.
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"
    assert _owner_pos(db_session_maker, y_id).status == "closed"
    for r in x_subs:
        assert _pos(db_session_maker, seed["strategy_id"], r.subscription_id).status == "closed"
    for r in y_subs:
        assert _pos(db_session_maker, y_id, r.subscription_id).status == "closed"

    # EVERY active subscriber forced to MANUAL ('offline').
    assert set(_active_sub_modes(db_session_maker)) == {"offline"}
    assert res["forced_manual"] == 3

    broker_spy.assert_not_called()


def test_master_emergency_idempotent(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    store = InProcessHaltStore()
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)
    _subs_with_positions(seed, db_session_maker, n=1)

    first = _master(db_session_maker, "drill", store)
    second = _master(db_session_maker, "drill", store)

    assert first["status"] == "halted" and first["closed"] == 2
    # Second call: everything already flat → closes nothing, still halted, subs
    # still offline. Safe no-op.
    assert second["status"] == "halted" and second["closed"] == 0
    assert second["halted"] is True
    assert set(_active_sub_modes(db_session_maker)) == {"offline"}
    broker_spy.assert_not_called()


def test_master_emergency_dormant_when_flag_off(
    client, seed, db_session_maker, broker_spy
):
    """Assumption under test: master-emergency respects the fanout flag →
    dormant when OFF; nothing closed, flag NOT tripped, subs untouched."""
    store = InProcessHaltStore()
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)
    subs = _subs_with_positions(seed, db_session_maker, n=1)

    res = _master(db_session_maker, "x", store)

    assert res["status"] == "dormant" and res["closed"] == 0
    assert is_platform_halted(store=store) is False          # NOT tripped
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "open"
    assert _pos(db_session_maker, seed["strategy_id"], subs[0].subscription_id).status == "open"
    assert set(_active_sub_modes(db_session_maker)) == {"auto"}   # untouched
    broker_spy.assert_not_called()
