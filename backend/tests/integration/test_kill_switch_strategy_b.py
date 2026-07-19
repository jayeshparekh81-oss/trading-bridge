"""KILL-SWITCH 3-TIER — TIER 2 (strategy kill → owner + cascade).

``KillSwitchService.kill_strategy(session, strategy_id)``:
  * closes the OWNER's positions FOR THAT STRATEGY ONLY (strategy_id == X AND
    subscription_id IS NULL) — reusing the same close primitives, STRATEGY-
    scoped so the user's OTHER strategies are untouched;
  * then cascade-closes every active subscriber's OWN mirrored positions
    (reusing Tier-1 kill_subscriber), per-subscriber isolated.

``_execute_emergency_square_off`` (the user-scoped account kill) is NOT called
and NOT edited → byte-identical + still available as its own thing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.services.kill_switch_service import KillSwitchService
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


def _kill_strategy(maker, strategy_id):
    async def _go():
        async with maker() as s:
            return await KillSwitchService().kill_strategy(s, strategy_id)

    return _run(_go())


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


# ═══════════════════════════════════════════════════════════════════════
# TIER 2 — strategy kill
# ═══════════════════════════════════════════════════════════════════════


def test_strategy_kill_closes_owner_and_all_subscribers(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)
    a, b = _subs_with_positions(seed, db_session_maker)

    res = _kill_strategy(db_session_maker, seed["strategy_id"])

    assert res["status"] == "killed"
    assert res["owner_closed"] == 1
    # OWNER closed …
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"
    # … AND both subscribers cascade-closed.
    for r in (a, b):
        row = _pos(db_session_maker, seed["strategy_id"], r.subscription_id)
        assert row.remaining_quantity == 0 and row.status == "closed"
    assert {x["status"] for x in res["subscribers"]} == {"killed"}
    broker_spy.assert_not_called()


def test_strategy_scoping_other_strategy_untouched(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    """THE over-close guard: user has strategy X and Y; kill_strategy(X) closes
    ONLY X's owner positions — Y's owner positions are UNTOUCHED."""
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)                       # X owner pos
    y_id = _run(_make_strategy_y(db_session_maker, seed))
    _owner_position(db_session_maker, seed, strategy_id=y_id)     # Y owner pos

    _kill_strategy(db_session_maker, seed["strategy_id"])         # kill X

    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"  # X closed
    y_row = _owner_pos(db_session_maker, y_id)
    assert y_row.remaining_quantity == 2 and y_row.status == "open"              # Y UNTOUCHED
    broker_spy.assert_not_called()


def test_cascade_scoping_other_strategy_subscriber_untouched(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    """A subscriber of a DIFFERENT strategy (Y) is NOT touched by kill X."""
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)
    x_subs = _subs_with_positions(seed, db_session_maker, n=1)
    y_id = _run(_make_strategy_y(db_session_maker, seed))
    y_subs = _subs_with_positions(seed, db_session_maker, strategy_id=y_id, n=1)

    _kill_strategy(db_session_maker, seed["strategy_id"])         # kill X

    x_row = _pos(db_session_maker, seed["strategy_id"], x_subs[0].subscription_id)
    y_row = _pos(db_session_maker, y_id, y_subs[0].subscription_id)
    assert x_row.status == "closed"                              # X's sub closed
    assert y_row.remaining_quantity == 2 and y_row.status == "open"  # Y's sub UNTOUCHED
    broker_spy.assert_not_called()


def test_per_subscriber_isolation(
    client, seed, db_session_maker, broker_spy, fanout_on, monkeypatch
):
    """One subscriber's close error does NOT block the owner or other subs."""
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)
    a, b = _subs_with_positions(seed, db_session_maker)

    real_kill = KillSwitchService.kill_subscriber

    async def _flaky(self, session, subscription_id):
        if subscription_id == a.subscription_id:
            raise RuntimeError("boom: sub A close failed")
        return await real_kill(self, session, subscription_id)

    monkeypatch.setattr(KillSwitchService, "kill_subscriber", _flaky)

    res = _kill_strategy(db_session_maker, seed["strategy_id"])

    assert res["owner_closed"] == 1                              # owner still closed
    by = {x["subscription_id"]: x for x in res["subscribers"]}
    assert by[str(a.subscription_id)]["status"] == "failed"      # A failed (isolated)
    assert by[str(b.subscription_id)]["status"] == "killed"      # B still closed
    b_row = _pos(db_session_maker, seed["strategy_id"], b.subscription_id)
    assert b_row.status == "closed"
    broker_spy.assert_not_called()


def test_strategy_kill_already_flat_is_noop(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    # No owner position, no subscribers → nothing to close.
    res = _kill_strategy(db_session_maker, seed["strategy_id"])
    assert res["status"] == "killed" and res["owner_closed"] == 0
    assert res["subscribers"] == []
    broker_spy.assert_not_called()


def test_strategy_kill_dormant_when_flag_off(
    client, seed, db_session_maker, broker_spy
):
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)
    a, _b = _subs_with_positions(seed, db_session_maker)

    res = _kill_strategy(db_session_maker, seed["strategy_id"])
    assert res["status"] == "dormant" and res["owner_closed"] == 0
    # owner + subscriber UNTOUCHED.
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "open"
    assert _pos(db_session_maker, seed["strategy_id"], a.subscription_id).status == "open"
    broker_spy.assert_not_called()


def test_no_subscriber_strategy_kill_owner_only(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    """BYTE-IDENTICAL owner behaviour: a no-subscriber strategy kill closes the
    owner's positions (strategy-scoped) and nothing else — exactly the owner
    close, no cascade. (BSE/CDSL/ANGELONE-shaped: zero subscribers.)"""
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)

    res = _kill_strategy(db_session_maker, seed["strategy_id"])

    assert res["status"] == "killed" and res["owner_closed"] == 1
    assert res["subscribers"] == []
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"
    broker_spy.assert_not_called()


def test_execute_emergency_square_off_still_works_unchanged(
    client, seed, db_session_maker, broker_spy
):
    """The user-scoped account kill is untouched and still available — closes
    ALL the user's positions (the account-wide kill), distinct from Tier 2."""
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    _owner_position(db_session_maker, seed)

    async def _go():
        async with db_session_maker() as s:
            actions, errors = await KillSwitchService()._execute_emergency_square_off(
                seed["user_id"], s)
            await s.commit()
            return actions, errors

    _run(_go())
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"
    broker_spy.assert_not_called()
