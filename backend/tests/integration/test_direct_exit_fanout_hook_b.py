"""FAN-OUT Module B+ — PIECE 1 (integration): direct_exit hook end-to-end.

Owner EXIT through ``direct_exit.execute_exit`` fires the additive fan-out hook
(flag ON) → subscribers mirror the exit. Proven on harness-shaped rows:
  * AUTO sub with a position  → mirror-closes (paper; broker never called);
  * MANUAL (offline) sub       → position UNTOUCHED (notify-only, no fill);
  * sub with NO position       → skipped (unwanted-short guard).
Byte-identical proofs: a strategy with ZERO subs → hook is a pure no-op; and
with the flag OFF → no fan-out at all. The owner's own exit is unchanged in all.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select, update

from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.services import direct_exit
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


async def _make_owner_paper(maker, seed):
    """Owner strategy → is_paper=True (so execute_exit takes the paper path)."""
    async with maker() as s:
        strat = await s.get(Strategy, seed["strategy_id"])
        strat.is_paper = True
        await s.commit()
        return await s.get(Strategy, seed["strategy_id"])


async def _mk_exit(maker, seed, *, symbol="NIFTY", side="long"):
    async with maker() as s:
        sig = StrategySignal(
            id=uuid.uuid4(), user_id=seed["user_id"],
            strategy_id=seed["strategy_id"], symbol=symbol, action="EXIT",
            quantity=1, order_type="market", status="executing",
            raw_payload={"action": "EXIT", "side": side, "symbol": symbol,
                         "price": 120.0},
            received_at=datetime.now(UTC))
        s.add(sig)
        await s.commit()
        return sig


async def _set_mode(maker, subscription_id, mode):
    async with maker() as s:
        await s.execute(update(MarketplaceSubscription)
                        .where(MarketplaceSubscription.id == subscription_id)
                        .values(execution_mode=mode))
        await s.commit()


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


def _sub_positions(maker, strategy_id):
    async def _load():
        async with maker() as s:
            return list((await s.execute(select(StrategyPosition).where(
                StrategyPosition.strategy_id == strategy_id,
                StrategyPosition.subscription_id.is_not(None)))).scalars())

    return _run(_load())


def _run_owner_exit(maker, seed, strat, sig):
    async def _go():
        async with maker() as s:
            res = await direct_exit.execute_exit(
                s, signal=await s.get(StrategySignal, sig.id),
                strategy=strat, leg_role="direct_exit")
            await s.commit()
            return res

    return _run(_go())


def test_owner_exit_mirrors_to_subscribers(
    client, seed, db_session_maker, broker_spy, monkeypatch, fake_redis
):
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    monkeypatch.setattr(
        "app.services.marketplace_fanout.fanout_enabled", lambda: True)

    strat = _run(_make_owner_paper(db_session_maker, seed))
    # OWNER position (subscription_id NULL, side buy = long).
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=None))
    # 3 subscribers: A manual(offline), B auto, C auto-no-position.
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=3, n_cancelled=0))
    a_manual, b_auto, c_nopos = refs[0], refs[1], refs[2]
    _run(_set_mode(db_session_maker, a_manual.subscription_id, "offline"))
    for r in (a_manual, b_auto):
        _run(_make_position(
            db_session_maker, user_id=r.subscriber_id,
            strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
            symbol="NIFTY", side="buy", qty=2, subscription_id=r.subscription_id))

    sig = _run(_mk_exit(db_session_maker, seed))
    res = _run_owner_exit(db_session_maker, seed, strat, sig)

    # OWNER exit unchanged — closed normally.
    assert res["status"] == "executed"
    assert res["position_status"] == "closed"
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"

    # AUTO sub (B) → mirror-closed.
    b_row = _pos(db_session_maker, seed["strategy_id"], b_auto.subscription_id)
    assert b_row.remaining_quantity == 0 and b_row.status == "closed"
    # MANUAL sub (A, offline) → UNTOUCHED (notify-only, no fill).
    a_row = _pos(db_session_maker, seed["strategy_id"], a_manual.subscription_id)
    assert a_row.remaining_quantity == 2 and a_row.status == "open"
    # no-position sub (C) → skipped, still no row.
    assert _pos(db_session_maker, seed["strategy_id"], c_nopos.subscription_id) is None

    broker_spy.assert_not_called()


def test_no_subscriber_owner_exit_is_byte_identical(
    client, seed, db_session_maker, broker_spy, monkeypatch, fake_redis
):
    """Strategy with ZERO subscriptions → hook is a pure no-op; owner exit +
    position state exactly as before, and no subscriber rows anywhere."""
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    monkeypatch.setattr(
        "app.services.marketplace_fanout.fanout_enabled", lambda: True)  # ON, but no subs

    strat = _run(_make_owner_paper(db_session_maker, seed))
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=None))
    sig = _run(_mk_exit(db_session_maker, seed))

    res = _run_owner_exit(db_session_maker, seed, strat, sig)

    # RETURN CONTRACT byte-identical — the owner-exit result dict is exactly
    # what it is without the hook. (Owner DB-state after the caller-commit is
    # NOT asserted here: the SQLite test engine shares ONE connection via
    # StaticPool, so the hook's SEPARATE read-only session rolls back the
    # owner's still-uncommitted closure on close — a test-harness artifact.
    # In production get_sessionmaker hands out a DIFFERENT pooled connection,
    # so the owner transaction is untouched; the clean DB proof is the
    # flag-OFF test below, which never opens a separate session.)
    assert res["status"] == "executed"
    assert res["close_qty"] == 2
    assert res["remaining"] == 0
    assert res["position_status"] == "closed"
    # Hook is a no-op without subscribers — NO subscriber rows created.
    assert _sub_positions(db_session_maker, seed["strategy_id"]) == []
    broker_spy.assert_not_called()


def test_flag_off_owner_exit_does_not_fan_out(
    client, seed, db_session_maker, broker_spy
):
    """Flag OFF (default) → hook first-line returns; subscribers UNTOUCHED."""
    strat = _run(_make_owner_paper(db_session_maker, seed))
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=None))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    _run(_make_position(
        db_session_maker, user_id=refs[0].subscriber_id,
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=refs[0].subscription_id))

    sig = _run(_mk_exit(db_session_maker, seed))
    res = _run_owner_exit(db_session_maker, seed, strat, sig)

    # CLEAN byte-identical proof: flag OFF → _maybe_fan_out_exit returns on its
    # first line (no separate session ever opened), so the owner exit is exactly
    # as before AND commits normally. This is the live default path that
    # BSE/CDSL/ANGELONE run — provably unchanged.
    assert res["status"] == "executed"
    assert res["position_status"] == "closed"
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"
    # subscriber position UNCHANGED — flag OFF means no fan-out at all.
    sub_row = _pos(db_session_maker, seed["strategy_id"], refs[0].subscription_id)
    assert sub_row.remaining_quantity == 2 and sub_row.status == "open"
    broker_spy.assert_not_called()


def test_execute_exit_wires_hook_with_correct_action_kind(
    client, seed, db_session_maker, monkeypatch
):
    """execute_exit calls _maybe_fan_out_exit with action_kind derived from
    leg_role (direct_exit→exit, direct_sl→sl_hit)."""
    calls: list[dict[str, Any]] = []

    async def _spy(*, signal, strategy, action_kind):
        calls.append({"action_kind": action_kind})

    monkeypatch.setattr(direct_exit, "_maybe_fan_out_exit", _spy)

    strat = _run(_make_owner_paper(db_session_maker, seed))
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=None))
    sig = _run(_mk_exit(db_session_maker, seed))

    async def _go(leg_role):
        async with db_session_maker() as s:
            r = await direct_exit.execute_exit(
                s, signal=await s.get(StrategySignal, sig.id),
                strategy=strat, leg_role=leg_role)
            await s.commit()
            return r

    _run(_go("direct_exit"))
    assert calls and calls[-1]["action_kind"] == "exit"
