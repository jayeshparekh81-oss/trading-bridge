"""LIVE broker-close for subscriber kill paths (Module B+) — MOCKED broker only.

When a subscription is NOT paper (``is_paper=False``), Tier-1/2/3 closes route
through the REAL broker primitives — :func:`_build_broker` +
:meth:`_close_position_via_broker` — scoped to the SUBSCRIBER'S OWN credential
(never the owner placeholder the position row carries, never another sub's).
Paper subscriptions still close via :meth:`_close_position_in_paper`, byte-
identical. Every broker here is a MOCK injected via the existing
``broker_factory`` seam — the real ``DhanBroker`` is spied and must NEVER fire.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import encrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.services.kill_switch_service import KillSwitchService
from tests.integration.test_marketplace_fanout_webhook import (
    _make_position,
    _run,
    _seed_listing_and_subs,
)


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "marketplace_fanout_enabled", True)


@pytest.fixture
def real_broker_spy(monkeypatch):
    """The REAL broker class must never fire — factory injection bypasses it."""
    from app.brokers.dhan import DhanBroker

    spy = MagicMock(name="place_order")
    monkeypatch.setattr(DhanBroker, "place_order", spy)
    return spy


class _MockBroker:
    """Async mock satisfying exactly what the close primitives call."""

    def __init__(self, creds):
        self.creds = creds
        self.orders: list = []

    async def is_session_valid(self):
        return True

    async def login(self):
        return None

    async def place_order(self, order):
        self.orders.append(order)
        return SimpleNamespace(
            broker_order_id=f"MOCK-{self.creds.client_id}",
            status=SimpleNamespace(value="complete"),
            message="mock fill",
        )


def _recording_factory(built: list):
    def factory(creds):
        b = _MockBroker(creds)
        built.append(b)
        return b

    return factory


async def _arm_live(maker, ref, client_id):
    """Give the subscriber their OWN active credential + flip the sub LIVE."""
    async with maker() as s:
        cred = BrokerCredential(
            user_id=ref.subscriber_id,
            broker_name="dhan",
            client_id_enc=encrypt_credential(client_id),
            api_key_enc=encrypt_credential(f"{client_id}-KEY"),
            api_secret_enc=encrypt_credential(f"{client_id}-SECRET"),
            access_token_enc=encrypt_credential(f"{client_id}-TOK"),
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            is_active=True,
        )
        s.add(cred)
        await s.flush()
        sub = await s.get(MarketplaceSubscription, ref.subscription_id)
        sub.is_paper = False
        sub.broker_credential_id = cred.id
        await s.commit()
        return str(cred.id)


async def _flip_live_no_cred(maker, ref):
    async with maker() as s:
        sub = await s.get(MarketplaceSubscription, ref.subscription_id)
        sub.is_paper = False
        await s.commit()


async def _make_owner_paper(maker, strategy_id):
    async with maker() as s:
        strat = await s.get(Strategy, strategy_id)
        strat.is_paper = True
        await s.commit()


def _pos_row(maker, subscription_id):
    async def _load():
        async with maker() as s:
            return (
                await s.execute(
                    select(StrategyPosition).where(
                        StrategyPosition.subscription_id == subscription_id
                    )
                )
            ).scalars().first()

    return _run(_load())


def _seed_scene(seed, maker, *, n_active=1):
    """Listing + N active subs, one open position each (owner-placeholder cred
    on the row — the trap the credential-scoping fix must never use)."""
    refs = _run(_seed_listing_and_subs(
        maker, strategy_id=seed["strategy_id"], creator_id=seed["user_id"],
        n_active=n_active, n_cancelled=0))
    for r in refs:
        _run(_make_position(
            maker, user_id=r.subscriber_id, strategy_id=seed["strategy_id"],
            credential_id=seed["credential_id"],  # owner placeholder on the ROW
            symbol="NIFTY", side="buy", qty=2, subscription_id=r.subscription_id))
    return refs


# ═══════════════════════════════════════════════════════════════════════
# 1) PAPER unchanged — byte-identical, broker never built
# ═══════════════════════════════════════════════════════════════════════


def test_paper_subscriber_kill_unchanged_no_broker(
    client, seed, db_session_maker, flag_on, real_broker_spy
):
    refs = _seed_scene(seed, db_session_maker)  # sub is_paper stays True (default)
    built: list = []

    async def _go():
        async with db_session_maker() as s:
            return await KillSwitchService().kill_subscriber(
                s, refs[0].subscription_id,
                broker_factory=_recording_factory(built))

    res = _run(_go())

    assert res["status"] == "killed" and res["closed"] == 1
    assert built == []                       # factory NEVER invoked in paper
    real_broker_spy.assert_not_called()      # real broker NEVER fired
    # Paper return shape byte-identical — the live-only keys must NOT appear.
    assert "mode" not in res and "errors" not in res
    row = _pos_row(db_session_maker, refs[0].subscription_id)
    assert row.status == "closed"
    assert row.action_history[-1]["broker_order_id"].startswith("PAPER-KILL-SWITCH-")


# ═══════════════════════════════════════════════════════════════════════
# 2) LIVE — routed to the SUBSCRIBER'S OWN credential (mocked)
# ═══════════════════════════════════════════════════════════════════════


def test_live_subscriber_close_routes_to_own_credential(
    client, seed, db_session_maker, flag_on, real_broker_spy
):
    refs = _seed_scene(seed, db_session_maker)
    own_cred_id = _run(_arm_live(db_session_maker, refs[0], "SUB-A-CID"))
    built: list = []

    async def _go():
        async with db_session_maker() as s:
            return await KillSwitchService().kill_subscriber(
                s, refs[0].subscription_id,
                broker_factory=_recording_factory(built))

    res = _run(_go())

    assert res["status"] == "killed" and res["closed"] == 1
    assert res["mode"] == "live" and res["errors"] == []
    assert res["resolved_credential_id"] == own_cred_id
    # ONE broker client, built from the SUBSCRIBER'S OWN credential — never the
    # owner's seed credential ("DHAN-CID"), never any other value.
    assert len(built) == 1
    assert built[0].creds.client_id == "SUB-A-CID"
    # The close order itself: opposing side, full remaining qty.
    assert len(built[0].orders) == 1
    order = built[0].orders[0]
    assert order.side.value == "sell" and order.quantity == 2
    real_broker_spy.assert_not_called()
    row = _pos_row(db_session_maker, refs[0].subscription_id)
    assert row.status == "closed" and row.exit_reason == "kill_switch"
    assert row.action_history[-1]["broker_order_id"] == "MOCK-SUB-A-CID"


# ═══════════════════════════════════════════════════════════════════════
# 3) MIXED — paper sub via paper, live sub via mock broker, owner paper
# ═══════════════════════════════════════════════════════════════════════


def test_mixed_paper_and_live_subscribers_route_correctly(
    client, seed, db_session_maker, flag_on, real_broker_spy
):
    _run(_make_owner_paper(db_session_maker, seed["strategy_id"]))
    refs = _seed_scene(seed, db_session_maker, n_active=2)
    # refs[0] stays PAPER; refs[1] goes LIVE with their own cred.
    _run(_arm_live(db_session_maker, refs[1], "SUB-B-CID"))
    # Owner's own open position (paper).
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=4, subscription_id=None))
    built: list = []

    async def _go():
        async with db_session_maker() as s:
            return await KillSwitchService().kill_strategy(
                s, seed["strategy_id"],
                broker_factory=_recording_factory(built))

    res = _run(_go())

    assert res["status"] == "killed"
    assert res["owner_closed"] == 1 and res["owner_errors"] == []
    assert [x["status"] for x in res["subscribers"]] == ["killed", "killed"]
    # Exactly ONE broker client — for the LIVE sub's OWN cred; paper never builds.
    assert [b.creds.client_id for b in built] == ["SUB-B-CID"]
    real_broker_spy.assert_not_called()
    paper_row = _pos_row(db_session_maker, refs[0].subscription_id)
    live_row = _pos_row(db_session_maker, refs[1].subscription_id)
    assert paper_row.status == "closed"
    assert paper_row.action_history[-1]["broker_order_id"].startswith(
        "PAPER-KILL-SWITCH-")
    assert live_row.status == "closed"
    assert live_row.action_history[-1]["broker_order_id"] == "MOCK-SUB-B-CID"


# ═══════════════════════════════════════════════════════════════════════
# 4) ISOLATION — one live sub's broker error blocks nobody else
# ═══════════════════════════════════════════════════════════════════════


def test_live_broker_error_isolated_from_owner_and_other_subs(
    client, seed, db_session_maker, flag_on, real_broker_spy
):
    _run(_make_owner_paper(db_session_maker, seed["strategy_id"]))
    refs = _seed_scene(seed, db_session_maker, n_active=2)
    _run(_arm_live(db_session_maker, refs[0], "SUB-A-CID"))   # healthy live
    _run(_arm_live(db_session_maker, refs[1], "SUB-B-CID"))   # broker will blow
    _run(_make_position(
        db_session_maker, user_id=seed["user_id"],
        strategy_id=seed["strategy_id"], credential_id=seed["credential_id"],
        symbol="NIFTY", side="buy", qty=4, subscription_id=None))
    built: list = []

    def _factory(creds):
        if creds.client_id == "SUB-B-CID":
            raise RuntimeError("broker down for B")
        b = _MockBroker(creds)
        built.append(b)
        return b

    async def _go():
        async with db_session_maker() as s:
            return await KillSwitchService().kill_strategy(
                s, seed["strategy_id"], broker_factory=_factory)

    res = _run(_go())

    # Owner closed despite B's failure.
    assert res["owner_closed"] == 1
    by_sub = {x["subscription_id"]: x for x in res["subscribers"]}
    a = by_sub[str(refs[0].subscription_id)]
    b = by_sub[str(refs[1].subscription_id)]
    assert a["status"] == "killed" and a["closed"] == 1
    assert b["status"] == "failed" and b["closed"] == 0
    assert b["errors"] and "broker down for B" in b["errors"][0]
    # A's close went through A's OWN cred; B's broker was never built.
    assert [x.creds.client_id for x in built] == ["SUB-A-CID"]
    assert _pos_row(db_session_maker, refs[0].subscription_id).status == "closed"
    assert _pos_row(db_session_maker, refs[1].subscription_id).status in (
        "open", "partial")                    # honestly NOT closed
    real_broker_spy.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# 5) LIVE with NO credential — fails honestly, no crash, nothing closed
# ═══════════════════════════════════════════════════════════════════════


def test_live_subscriber_without_credential_fails_honestly(
    client, seed, db_session_maker, flag_on, real_broker_spy
):
    refs = _seed_scene(seed, db_session_maker)
    _run(_flip_live_no_cred(db_session_maker, refs[0]))  # LIVE but zero creds
    built: list = []

    async def _go():
        async with db_session_maker() as s:
            return await KillSwitchService().kill_subscriber(
                s, refs[0].subscription_id,
                broker_factory=_recording_factory(built))

    res = _run(_go())

    assert res["status"] == "failed" and res["closed"] == 0
    assert res["errors"] and "credential" in res["errors"][0]
    assert built == []
    real_broker_spy.assert_not_called()
    assert _pos_row(db_session_maker, refs[0].subscription_id).status in (
        "open", "partial")


# ═══════════════════════════════════════════════════════════════════════
# 6) Flag OFF — dormant, even for a LIVE sub (no broker, nothing closed)
# ═══════════════════════════════════════════════════════════════════════


def test_flag_off_dormant_even_when_live(
    client, seed, db_session_maker, real_broker_spy
):
    refs = _seed_scene(seed, db_session_maker)
    _run(_arm_live(db_session_maker, refs[0], "SUB-A-CID"))
    built: list = []

    async def _go():
        async with db_session_maker() as s:
            return await KillSwitchService().kill_subscriber(
                s, refs[0].subscription_id,
                broker_factory=_recording_factory(built))

    res = _run(_go())

    assert res["status"] == "dormant" and res["closed"] == 0
    assert built == []
    real_broker_spy.assert_not_called()
    assert _pos_row(db_session_maker, refs[0].subscription_id).status in (
        "open", "partial")
