"""FAN-OUT Module B — subscriber EXIT logic (hardening ``fan_out_exit``).

Test-FIRST for the exit path Module A left UNTESTED. Everything here lives
inside the dormant ``marketplace_fanout`` module; the paper stub holds
throughout — the real broker ``place_order`` is asserted never called.

Covered:
  mirror exit (AUTO) — owner PARTIAL 50% closes 50% of the SUBSCRIBER'S OWN
                       qty; EXIT/SL_HIT full-close at payload price, STORED
                       symbol (never re-resolved).
  AUTO vs MANUAL     — AUTO subs get a paper mirror-fill; a MANUAL sub gets a
                       ``notify_only`` result (message payload) and NEVER a
                       fill (not even the ``_simulate_fill`` primitive).
  position-check     — no sub position -> ``skipped_no_position`` (the loud
                       unwanted-short guard).
  idempotency        — the same owner-exit fanned twice never double-closes.
  isolation          — one subscriber's failure never blocks the others.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.services.marketplace_fanout import PaperPositionProvider, fan_out_exit
from tests.integration.test_marketplace_fanout_webhook import (
    _make_position,
    _run,
    _seed_listing_and_subs,
)


# ── local helpers (mirror test_fanout_p0.py's style) ──────────────────────
async def _mk_signal(maker, seed, *, action: str, symbol: str = "NIFTY",
                     payload: dict | None = None):
    base: dict[str, Any] = {"action": action, "side": "long", "symbol": symbol,
                            "price": 100.0}
    if payload:
        base.update(payload)
    async with maker() as s:
        sig = StrategySignal(
            id=uuid.uuid4(), user_id=seed["user_id"],
            strategy_id=seed["strategy_id"], symbol=symbol, action=action,
            quantity=1, order_type="market", status="executed",
            raw_payload=base, received_at=datetime.now(UTC))
        s.add(sig)
        await s.commit()
        return sig


async def _strategy(maker, seed) -> Strategy:
    async with maker() as s:
        return await s.get(Strategy, seed["strategy_id"])


def _sub_rows(maker, strategy_id):
    async def _load():
        async with maker() as s:
            return list((await s.execute(
                select(StrategyPosition).where(
                    StrategyPosition.strategy_id == strategy_id,
                    StrategyPosition.subscription_id.is_not(None)))).scalars())

    return _run(_load())


def _row_for(maker, strategy_id, subscription_id):
    for r in _sub_rows(maker, strategy_id):
        if r.subscription_id == subscription_id:
            return r
    return None


def _manual(ref):
    return replace(ref, execution_mode="manual")


def _auto(ref):
    return replace(ref, execution_mode="auto")


@pytest.fixture
def broker_spy(monkeypatch):
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    return spy


# ═══════════════════════════════════════════════════════════════════════
# MIRROR EXIT + AUTO/MANUAL
# ═══════════════════════════════════════════════════════════════════════


def test_partial_auto_closes_half_manual_notify_only(
    client, seed, db_session_maker, broker_spy
):
    """Owner 50% partial: AUTO sub (holds 8) closes 4 of ITS OWN qty; MANUAL
    sub (holds 8) gets notify_only for 4 and is NOT filled."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=2, n_cancelled=0))
    auto_ref, manual_ref = _auto(refs[0]), _manual(refs[1])
    for r in (auto_ref, manual_ref):
        _run(_make_position(
            db_session_maker, user_id=r.subscriber_id,
            strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
            symbol="NIFTY", side="buy", qty=8,
            subscription_id=r.subscription_id))

    sig = _run(_mk_signal(db_session_maker, seed, action="PARTIAL",
                          payload={"closePct": 50, "price": 110.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=[auto_ref, manual_ref],
                db=s, action_kind="partial")

    by = {r.subscription_id: r for r in _run(_go())}

    # AUTO — mirror-filled 50% of its OWN 8 = 4.
    assert by[auto_ref.subscription_id].status == "filled"
    assert by[auto_ref.subscription_id].quantity == 4
    # MANUAL — notify_only, message present, NO fill.
    m = by[manual_ref.subscription_id]
    assert m.status == "notify_only"
    assert m.quantity == 4
    assert m.broker_order_id is None and m.avg_price is None
    assert m.notify_message and "manual" in m.notify_message.lower()

    # AUTO row drops to 4/partial; MANUAL row is UNTOUCHED at 8/open.
    assert _row_for(
        db_session_maker, seed["strategy_id"],
        auto_ref.subscription_id).remaining_quantity == 4
    manual_row = _row_for(
        db_session_maker, seed["strategy_id"], manual_ref.subscription_id)
    assert manual_row.remaining_quantity == 8 and manual_row.status == "open"
    broker_spy.assert_not_called()


@pytest.mark.parametrize("kind", ["exit", "sl_hit"])
def test_full_exit_auto_flat_noposition_skipped(
    client, seed, db_session_maker, broker_spy, kind
):
    """Owner full exit: AUTO sub with a position goes flat (stored symbol); a
    sub with NO position → skipped_no_position (loud), no row created."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=2, n_cancelled=0))
    held, empty = _auto(refs[0]), _auto(refs[1])
    _run(_make_position(
        db_session_maker, user_id=held.subscriber_id,
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=6, subscription_id=held.subscription_id))

    sig = _run(_mk_signal(db_session_maker, seed, action=kind.upper(),
                          payload={"price": 120.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=[held, empty], db=s,
                action_kind=kind)

    by = {r.subscription_id: r for r in _run(_go())}
    assert by[held.subscription_id].status == "filled"
    assert by[held.subscription_id].quantity == 6
    assert by[empty.subscription_id].status == "skipped_no_position"

    held_row = _row_for(
        db_session_maker, seed["strategy_id"], held.subscription_id)
    assert held_row.remaining_quantity == 0 and held_row.status == "closed"
    assert held_row.symbol == "NIFTY"          # STORED symbol, never re-resolved
    assert _row_for(
        db_session_maker, seed["strategy_id"], empty.subscription_id) is None
    broker_spy.assert_not_called()


def test_manual_exit_never_simulates_a_fill(
    client, seed, db_session_maker, broker_spy, monkeypatch
):
    """A MANUAL exit does not even touch the ``_simulate_fill`` primitive, and
    the subscriber's position is left completely unchanged."""
    import app.services.strategy_executor as se

    sim_spy = MagicMock(wraps=se._simulate_fill)
    monkeypatch.setattr(se, "_simulate_fill", sim_spy)

    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    manual = _manual(refs[0])
    _run(_make_position(
        db_session_maker, user_id=manual.subscriber_id,
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=4,
        subscription_id=manual.subscription_id))

    sig = _run(_mk_signal(db_session_maker, seed, action="EXIT",
                          payload={"price": 120.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=[manual], db=s,
                action_kind="exit")

    results = _run(_go())
    assert results[0].status == "notify_only"

    row = _row_for(db_session_maker, seed["strategy_id"], manual.subscription_id)
    assert row.remaining_quantity == 4 and row.status == "open"
    sim_spy.assert_not_called()         # paper fill primitive never touched
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# IDEMPOTENCY + ISOLATION
# ═══════════════════════════════════════════════════════════════════════


def test_double_fanned_exit_is_idempotent(
    client, seed, db_session_maker, broker_spy, monkeypatch, fake_redis
):
    """The same owner exit (same signal_hash) fanned twice closes ONCE."""
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    auto = _auto(refs[0])
    _run(_make_position(
        db_session_maker, user_id=auto.subscriber_id,
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=6, subscription_id=auto.subscription_id))

    sig = _run(_mk_signal(db_session_maker, seed, action="EXIT",
                          payload={"price": 120.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=[auto], db=s,
                action_kind="exit", signal_hash="H-fixed")

    first = _run(_go())
    second = _run(_go())
    assert first[0].status == "filled"
    assert second[0].status == "duplicate"     # NOT re-closed

    row = _row_for(db_session_maker, seed["strategy_id"], auto.subscription_id)
    assert row.remaining_quantity == 0 and row.status == "closed"

    async def _legs():
        async with db_session_maker() as s:
            from app.db.models.strategy_execution import StrategyExecution

            return list((await s.execute(
                select(StrategyExecution).where(
                    StrategyExecution.subscription_id == auto.subscription_id,
                    StrategyExecution.leg_role == "exit"))).scalars())

    assert len(_run(_legs())) == 1            # exactly ONE close leg
    broker_spy.assert_not_called()


def test_one_subscriber_error_is_isolated(
    client, seed, db_session_maker, broker_spy
):
    """One subscriber's provider error → status 'failed'; the OTHER subscriber
    still closes normally."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=2, n_cancelled=0))
    bad, good = _auto(refs[0]), _auto(refs[1])
    for r in (bad, good):
        _run(_make_position(
            db_session_maker, user_id=r.subscriber_id,
            strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
            symbol="NIFTY", side="buy", qty=4,
            subscription_id=r.subscription_id))

    sig = _run(_mk_signal(db_session_maker, seed, action="EXIT",
                          payload={"price": 120.0}))

    class _OneError(PaperPositionProvider):
        def __init__(self, fail_id):
            self._fail = fail_id

        async def find_open(self, db, *, strategy_id, subscription_id):
            if subscription_id == self._fail:
                raise RuntimeError("boom: simulated provider failure")
            return await super().find_open(
                db, strategy_id=strategy_id, subscription_id=subscription_id)

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=[bad, good], db=s,
                action_kind="exit",
                position_provider=_OneError(bad.subscription_id))

    by = {r.subscription_id: r for r in _run(_go())}
    assert by[bad.subscription_id].status == "failed"
    assert "boom" in (by[bad.subscription_id].error or "")
    assert by[good.subscription_id].status == "filled"      # unaffected

    good_row = _row_for(
        db_session_maker, seed["strategy_id"], good.subscription_id)
    assert good_row.remaining_quantity == 0 and good_row.status == "closed"
    broker_spy.assert_not_called()


def test_broker_never_called_on_any_exit_path(
    client, seed, db_session_maker, broker_spy
):
    """One fan-out that exercises fill + notify_only + skip: the real broker
    place_order is never invoked on ANY of the three paths."""
    strat = _run(_strategy(db_session_maker, seed))
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=3, n_cancelled=0))
    auto, manual, empty = _auto(refs[0]), _manual(refs[1]), _auto(refs[2])
    for r in (auto, manual):
        _run(_make_position(
            db_session_maker, user_id=r.subscriber_id,
            strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
            symbol="NIFTY", side="buy", qty=4,
            subscription_id=r.subscription_id))

    sig = _run(_mk_signal(db_session_maker, seed, action="EXIT",
                          payload={"price": 120.0}))

    async def _go():
        async with db_session_maker() as s:
            return await fan_out_exit(
                signal=sig, strategy=strat, subscribers=[auto, manual, empty],
                db=s, action_kind="exit")

    statuses = {r.subscription_id: r.status for r in _run(_go())}
    assert statuses[auto.subscription_id] == "filled"
    assert statuses[manual.subscription_id] == "notify_only"
    assert statuses[empty.subscription_id] == "skipped_no_position"
    broker_spy.assert_not_called()
