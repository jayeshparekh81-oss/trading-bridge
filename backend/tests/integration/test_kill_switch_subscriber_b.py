"""KILL-SWITCH 3-TIER — TIER 1 (subscriber kill).

``KillSwitchService.kill_subscriber(session, subscription_id)`` closes ONLY that
subscriber's OWN open mirrored positions, scoped to the SUBSCRIBER'S own
credential (the audit-flagged fix — never the owner placeholder, never another
subscriber). Paper stage: broker place_order NEVER invoked. Idempotent.

BYTE-IDENTICAL invariant: the owner ``_execute_emergency_square_off`` path is
untouched — it filters by ``user_id`` and never sees a subscriber's rows (they
carry the subscriber's user_id). BSE/CDSL/ANGELONE (zero subscribers) unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import encrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.schemas.broker import BrokerName
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


async def _make_cred(maker, user_id):
    async with maker() as s:
        cred = BrokerCredential(
            user_id=user_id, broker_name=BrokerName.DHAN,
            client_id_enc=encrypt_credential("SUB-CID"),
            api_key_enc=encrypt_credential("SUB-KEY"),
            api_secret_enc=encrypt_credential("SUB-SECRET"),
            access_token_enc=encrypt_credential("SUB-TOK"),
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC), is_active=True)
        s.add(cred)
        await s.commit()
        return cred.id


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


def _kill(maker, subscription_id):
    async def _go():
        async with maker() as s:
            return await KillSwitchService().kill_subscriber(s, subscription_id)

    return _run(_go())


def _two_subs_with_positions(seed, maker):
    refs = _run(_seed_listing_and_subs(
        maker, strategy_id=seed["strategy_id"], creator_id=seed["user_id"],
        n_active=2, n_cancelled=0))
    for r in refs:
        _run(_make_position(
            maker, user_id=r.subscriber_id, strategy_id=seed["strategy_id"],
            credential_id=seed["credential_id"], symbol="NIFTY", side="buy",
            qty=2, subscription_id=r.subscription_id))
    return refs


# ═══════════════════════════════════════════════════════════════════════
# TIER 1 — subscriber kill
# ═══════════════════════════════════════════════════════════════════════


def test_kill_subscriber_a_closes_only_a(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    a, b = _two_subs_with_positions(seed, db_session_maker)

    res = _kill(db_session_maker, a.subscription_id)

    assert res["status"] == "killed" and res["closed"] == 1
    a_row = _pos(db_session_maker, seed["strategy_id"], a.subscription_id)
    b_row = _pos(db_session_maker, seed["strategy_id"], b.subscription_id)
    assert a_row.remaining_quantity == 0 and a_row.status == "closed"   # A killed
    assert b_row.remaining_quantity == 2 and b_row.status == "open"     # B untouched
    broker_spy.assert_not_called()


def test_kill_subscriber_b_closes_only_b(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    a, b = _two_subs_with_positions(seed, db_session_maker)

    res = _kill(db_session_maker, b.subscription_id)

    assert res["status"] == "killed" and res["closed"] == 1
    a_row = _pos(db_session_maker, seed["strategy_id"], a.subscription_id)
    b_row = _pos(db_session_maker, seed["strategy_id"], b.subscription_id)
    assert b_row.remaining_quantity == 0 and b_row.status == "closed"   # B killed
    assert a_row.remaining_quantity == 2 and a_row.status == "open"     # A untouched
    broker_spy.assert_not_called()


def test_kill_subscriber_already_flat_is_noop(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    refs = _run(_seed_listing_and_subs(
        db_session_maker, strategy_id=seed["strategy_id"],
        creator_id=seed["user_id"], n_active=1, n_cancelled=0))
    # NO position for this subscriber → already flat.
    res = _kill(db_session_maker, refs[0].subscription_id)
    assert res["status"] == "already_flat" and res["closed"] == 0
    broker_spy.assert_not_called()


def test_kill_subscriber_uses_own_credential_not_owner_placeholder(
    client, seed, db_session_maker, broker_spy, fanout_on
):
    """The scoping fix: the resolved credential is the SUBSCRIBER'S own, never
    the owner placeholder the position row carries."""
    a, _b = _two_subs_with_positions(seed, db_session_maker)
    sub_cred_id = _run(_make_cred(db_session_maker, a.subscriber_id))

    res = _kill(db_session_maker, a.subscription_id)

    assert res["status"] == "killed"
    assert res["credential_scope"] == "subscriber_own"
    # resolved = the subscriber's OWN cred, NOT the owner placeholder.
    assert res["resolved_credential_id"] == str(sub_cred_id)
    assert res["resolved_credential_id"] != str(seed["credential_id"])
    broker_spy.assert_not_called()


def test_kill_subscriber_dormant_when_flag_off(
    client, seed, db_session_maker, broker_spy
):
    """Flag OFF (default) → dormant no-op; positions untouched."""
    a, _b = _two_subs_with_positions(seed, db_session_maker)
    res = _kill(db_session_maker, a.subscription_id)
    assert res["status"] == "dormant" and res["closed"] == 0
    a_row = _pos(db_session_maker, seed["strategy_id"], a.subscription_id)
    assert a_row.remaining_quantity == 2 and a_row.status == "open"     # untouched
    broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# BYTE-IDENTICAL — owner square-off never touches subscriber rows
# ═══════════════════════════════════════════════════════════════════════


def test_owner_square_off_ignores_subscriber_positions(
    client, seed, db_session_maker, broker_spy
):
    """The UNCHANGED owner path (_execute_emergency_square_off, filtered by
    user_id) closes ONLY the owner's rows; a subscriber's mirrored position
    (different user_id) is untouched — the no-subscriber BSE/CDSL/ANGELONE
    behaviour is structurally identical."""
    _run(_make_paper(db_session_maker, seed["strategy_id"]))
    # Owner position (owner user_id, subscription NULL).
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=2, subscription_id=None))
    # A subscriber with a mirrored position (subscriber user_id).
    a, _b = _two_subs_with_positions(seed, db_session_maker)

    async def _go():
        async with db_session_maker() as s:
            actions, errors = await KillSwitchService()._execute_emergency_square_off(
                seed["user_id"], s)
            await s.commit()
            return actions, errors

    _run(_go())

    # OWNER position closed by the owner kill …
    assert _owner_pos(db_session_maker, seed["strategy_id"]).status == "closed"
    # … but the SUBSCRIBER position is UNTOUCHED (owner path never saw it).
    a_row = _pos(db_session_maker, seed["strategy_id"], a.subscription_id)
    assert a_row.remaining_quantity == 2 and a_row.status == "open"
    broker_spy.assert_not_called()
