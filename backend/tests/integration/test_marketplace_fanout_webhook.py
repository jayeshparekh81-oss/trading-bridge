"""Marketplace Module 3 — subscription_id scoping: isolation + paper persistence.

Proves, against the real (sqlite) DB + the live webhook handler + the shared
executor lookups:

    resolve  — ``resolve_active_subscriptions`` is read-only + active-only.
    flag off — the fan-out block never runs; owner dispatches exactly once.
    persist  — flag on: one ISOLATED subscriber PAPER position+execution per
               active subscriber (tagged subscription_id), owner dispatches once,
               zero live-order calls.
    owner BI — owner open-position lookups (entry-sum + exit) scope to
               ``subscription_id IS NULL`` and return the OWNER row even when a
               subscriber row exists on the same (strategy, symbol, side).
    3-way    — owner + 2 subscribers on the same (strategy, symbol, side) =>
               three fully isolated positions, NO quantity bleed; each
               subscriber sums only within its own scope.
    paper    — dispatch makes ZERO real-broker / live-order calls even when the
               strategy is LIVE (is_paper=False).

Uses the shared ``tests/integration/conftest.py`` harness (paper mode forced,
fake Redis, Celery eager, HMAC). The owner ``dispatch_signal`` is mocked to a
no-op spy where we want to isolate the fast path.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import encrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.schemas.broker import BrokerName, OrderSide
from app.services.direct_exit import get_open_position
from app.services.marketplace_fanout import (
    SubscriberRef,
    dispatch_subscriber_executions,
    resolve_active_subscriptions,
    resolve_subscriber_credential,
)
from app.services.strategy_executor import _find_existing_open_position
from tests.integration.conftest import HMAC_HEADER, _sign

# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _entry_payload(**overrides: Any) -> bytes:
    base: dict[str, Any] = {
        "action": "BUY",
        "symbol": "NIFTY",
        "quantity": 1,
        "order_type": "market",
        "price": 22500.0,
    }
    base.update(overrides)
    return json.dumps(base).encode("utf-8")


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


def _force_flag(monkeypatch: Any, value: bool) -> None:
    """Set MARKETPLACE_FANOUT_ENABLED deterministically and rebuild settings."""
    from app.core import config as _config

    monkeypatch.setenv("MARKETPLACE_FANOUT_ENABLED", "true" if value else "false")
    _config.get_settings.cache_clear()


async def _seed_listing_and_subs(
    maker: async_sessionmaker[AsyncSession],
    *,
    strategy_id: uuid.UUID,
    creator_id: uuid.UUID,
    n_active: int = 2,
    n_cancelled: int = 1,
    lots_overrides: list[int | None] | None = None,
    broker_credential_ids: list[uuid.UUID | None] | None = None,
) -> list[SubscriberRef]:
    """Publish a listing for ``strategy_id`` + N active and M cancelled subs.

    Returns the active subscriptions as :class:`SubscriberRef`s. Each subscriber
    is its own bare User row (FK-valid).
    """
    active: list[SubscriberRef] = []
    async with maker() as s:
        listing = MarketplaceListing(
            strategy_id=strategy_id,
            creator_id=creator_id,
            title="fanout-test-listing",
            status="published",
        )
        s.add(listing)
        await s.flush()

        for i in range(n_active):
            u = User(email=f"sub-active-{i}-{uuid.uuid4().hex}@t.com", password_hash="x")
            s.add(u)
            await s.flush()
            lots = lots_overrides[i] if lots_overrides else None
            cred = broker_credential_ids[i] if broker_credential_ids else None
            sub = MarketplaceSubscription(
                listing_id=listing.id,
                subscriber_id=u.id,
                subscribed_at=datetime.now(UTC),
                status="active",
                amount_paid_inr=Decimal("0"),
                lots_override=lots,
                broker_credential_id=cred,
            )
            s.add(sub)
            await s.flush()
            active.append(
                SubscriberRef(
                    subscription_id=sub.id,
                    subscriber_id=u.id,
                    listing_id=listing.id,
                    status="active",
                    subscribed_at=sub.subscribed_at,
                    access_until=None,
                    lots_override=lots,
                    broker_credential_id=cred,
                )
            )

        for i in range(n_cancelled):
            u = User(email=f"sub-cancel-{i}-{uuid.uuid4().hex}@t.com", password_hash="x")
            s.add(u)
            await s.flush()
            s.add(
                MarketplaceSubscription(
                    listing_id=listing.id,
                    subscriber_id=u.id,
                    subscribed_at=datetime.now(UTC),
                    status="cancelled",
                    amount_paid_inr=Decimal("0"),
                )
            )

        await s.commit()
    return active


async def _make_position(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    credential_id: uuid.UUID,
    symbol: str,
    side: str,
    qty: int,
    subscription_id: uuid.UUID | None,
) -> uuid.UUID:
    """Insert one open StrategyPosition (owner row when subscription_id is None)."""
    async with maker() as s:
        pos = StrategyPosition(
            user_id=user_id,
            strategy_id=strategy_id,
            broker_credential_id=credential_id,
            subscription_id=subscription_id,
            symbol=symbol.upper(),
            side=side,
            total_quantity=qty,
            remaining_quantity=qty,
            status="open",
            opened_at=datetime.now(UTC),
        )
        s.add(pos)
        await s.commit()
        return pos.id


async def _seed_signal(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    symbol: str = "NIFTY",
    action: str = "BUY",
    side: str = "long",
) -> StrategySignal:
    async with maker() as s:
        sig = StrategySignal(
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            action=action,
            raw_payload={"side": side, "price": 100.0},
            status="received",
        )
        s.add(sig)
        await s.commit()
        return sig  # detached; expire_on_commit=False keeps attrs loaded


async def _load_strategy(
    maker: async_sessionmaker[AsyncSession], strategy_id: uuid.UUID
) -> Strategy:
    async with maker() as s:
        return await s.get(Strategy, strategy_id)


async def _positions(
    maker: async_sessionmaker[AsyncSession],
    *,
    strategy_id: uuid.UUID,
    symbol: str | None = None,
    side: str | None = None,
) -> list[StrategyPosition]:
    async with maker() as s:
        stmt = select(StrategyPosition).where(
            StrategyPosition.strategy_id == strategy_id
        )
        if symbol is not None:
            stmt = stmt.where(StrategyPosition.symbol == symbol.upper())
        if side is not None:
            stmt = stmt.where(StrategyPosition.side == side)
        return list((await s.execute(stmt)).scalars().all())


async def _count_executions_with_subscription(
    maker: async_sessionmaker[AsyncSession],
) -> int:
    async with maker() as s:
        return (
            await s.execute(
                select(func.count())
                .select_from(StrategyExecution)
                .where(StrategyExecution.subscription_id.is_not(None))
            )
        ).scalar_one()


# ═══════════════════════════════════════════════════════════════════════
# resolve_active_subscriptions — active-only + read-only
# ═══════════════════════════════════════════════════════════════════════


def test_resolve_returns_active_only_and_is_read_only(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
) -> None:
    async def _inner() -> tuple[list[Any], list[Any], int, int, tuple[set, set, set]]:
        refs = await _seed_listing_and_subs(
            db_session_maker,
            strategy_id=seed["strategy_id"],
            creator_id=seed["user_id"],
            n_active=2,
            n_cancelled=1,
        )
        async with db_session_maker() as s:
            before = (
                await s.execute(
                    select(func.count()).select_from(MarketplaceSubscription)
                )
            ).scalar_one()
            result = await resolve_active_subscriptions(seed["strategy_id"], s)
            after = (
                await s.execute(
                    select(func.count()).select_from(MarketplaceSubscription)
                )
            ).scalar_one()
            pending = (set(s.new), set(s.dirty), set(s.deleted))
        return refs, result, before, after, pending

    refs, result, before, after, pending = _run(_inner())

    assert len(result) == 2
    assert all(r.status == "active" for r in result)
    assert {r.subscription_id for r in result} == {r.subscription_id for r in refs}
    assert before == 3 and after == 3  # read-only — nothing added/removed
    assert pending == (set(), set(), set())


# ═══════════════════════════════════════════════════════════════════════
# Flag OFF — fan-out never runs, owner path unchanged
# ═══════════════════════════════════════════════════════════════════════


def test_flag_off_skips_fanout_and_owner_dispatches_once(
    client: Any,
    seed: dict[str, Any],
    monkeypatch: Any,
) -> None:
    _force_flag(monkeypatch, False)

    dispatched: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal",
        lambda sid, kind: dispatched.append((sid, kind)),
    )

    fanout_calls: list[Any] = []

    async def _dispatch_spy(*a: Any, **kw: Any) -> list[Any]:
        fanout_calls.append(kw)
        return []

    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_subscriber_executions", _dispatch_spy
    )

    body = _entry_payload()
    resp = client.post(
        _url(seed["token_plain"]),
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )

    assert resp.status_code == 202, resp.text
    assert len(dispatched) == 1, f"owner dispatch must fire exactly once, got {dispatched}"
    assert fanout_calls == [], "subscriber dispatch must be skipped when flag is OFF"


# ═══════════════════════════════════════════════════════════════════════
# Flag ON — persist isolated subscriber PAPER positions, no live order
# ═══════════════════════════════════════════════════════════════════════


def test_flag_on_persists_isolated_subscriber_paper_positions(
    client: Any,
    seed: dict[str, Any],
    db_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    _force_flag(monkeypatch, True)

    # Owner dispatch -> no-op spy so the eager worker never runs (isolates the
    # fast path + proves the fan-out adds no dispatch / no owner position).
    dispatched: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal",
        lambda sid, kind: dispatched.append((sid, kind)),
    )

    import app.services.strategy_executor as se

    sim_calls: list[Any] = []
    real_sim = se._simulate_fill

    def _sim_spy(signal: Any, quantity: int) -> Any:
        sim_calls.append((signal, quantity))
        return real_sim(signal, quantity)

    monkeypatch.setattr(se, "_simulate_fill", _sim_spy)

    live_calls: list[int] = []
    monkeypatch.setattr(
        se, "place_strategy_orders", lambda *a, **k: live_calls.append(1)
    )

    refs = _run(
        _seed_listing_and_subs(
            db_session_maker,
            strategy_id=seed["strategy_id"],
            creator_id=seed["user_id"],
            n_active=2,
            n_cancelled=1,
        )
    )

    body = _entry_payload()
    resp = client.post(
        _url(seed["token_plain"]),
        content=body,
        headers={HMAC_HEADER: _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 202, resp.text

    assert len(dispatched) == 1, f"fan-out must not dispatch; got {dispatched}"
    assert len(sim_calls) == 2, f"one paper fill per ACTIVE subscriber; got {len(sim_calls)}"
    assert live_calls == [], "subscribers must never hit the live execution entry"

    rows = _run(_positions(db_session_maker, strategy_id=seed["strategy_id"]))
    owner_rows = [r for r in rows if r.subscription_id is None]
    sub_rows = [r for r in rows if r.subscription_id is not None]

    assert owner_rows == [], "owner worker mocked — no owner position expected"
    assert len(sub_rows) == 2, "one isolated paper position per active subscriber"
    assert {r.subscription_id for r in sub_rows} == {r.subscription_id for r in refs}
    assert all(r.remaining_quantity == 1 for r in sub_rows)  # seed entry_lots=1, lot_size 1
    assert all(r.status == "open" for r in sub_rows)

    # Subscriber StrategyExecution rows are tagged with the subscription_id too.
    assert _run(_count_executions_with_subscription(db_session_maker)) == 2


# ═══════════════════════════════════════════════════════════════════════
# Owner byte-identical — owner lookups scope to subscription_id IS NULL
# ═══════════════════════════════════════════════════════════════════════


def test_owner_lookups_scope_to_null_unaffected_by_subscriber_rows(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
) -> None:
    async def _inner() -> tuple[Any, ...]:
        refs = await _seed_listing_and_subs(
            db_session_maker,
            strategy_id=seed["strategy_id"],
            creator_id=seed["user_id"],
            n_active=1,
            n_cancelled=0,
        )
        sub = refs[0]
        # Owner row (subscription_id NULL) + subscriber row on the SAME
        # (strategy, symbol, side).
        owner_id = await _make_position(
            db_session_maker,
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            credential_id=seed["credential_id"],
            symbol="NIFTY",
            side="buy",
            qty=10,
            subscription_id=None,
        )
        sub_pos_id = await _make_position(
            db_session_maker,
            user_id=sub.subscriber_id,
            strategy_id=seed["strategy_id"],
            credential_id=seed["credential_id"],
            symbol="NIFTY",
            side="buy",
            qty=3,
            subscription_id=sub.subscription_id,
        )
        async with db_session_maker() as s:
            owner_match = await _find_existing_open_position(
                s, strategy_id=seed["strategy_id"], symbol="NIFTY", side=OrderSide.BUY
            )
            scoped_match = await _find_existing_open_position(
                s,
                strategy_id=seed["strategy_id"],
                symbol="NIFTY",
                side=OrderSide.BUY,
                subscription_id=sub.subscription_id,
            )
            exit_match = await get_open_position(
                s, strategy_id=seed["strategy_id"], symbol="NIFTY", side="long"
            )
        return (
            owner_id,
            sub_pos_id,
            owner_match.id,
            owner_match.subscription_id,
            scoped_match.id,
            exit_match.id,
            exit_match.subscription_id,
        )

    (
        owner_id,
        sub_pos_id,
        om_id,
        om_sub,
        sm_id,
        ex_id,
        ex_sub,
    ) = _run(_inner())

    # Owner entry-sum lookup returns the OWNER row (NULL scope), never the
    # subscriber row — byte-identical to pre-column behaviour.
    assert om_id == owner_id
    assert om_sub is None
    # The scoped lookup returns the SUBSCRIBER row.
    assert sm_id == sub_pos_id
    # Owner exit lookup likewise returns the OWNER row only.
    assert ex_id == owner_id
    assert ex_sub is None


# ═══════════════════════════════════════════════════════════════════════
# 3-way isolation — owner + 2 subscribers, no quantity bleed
# ═══════════════════════════════════════════════════════════════════════


def test_three_isolated_positions_no_quantity_bleed(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
) -> None:
    async def _inner() -> tuple[uuid.UUID, list[SubscriberRef], list[StrategyPosition]]:
        refs = await _seed_listing_and_subs(
            db_session_maker,
            strategy_id=seed["strategy_id"],
            creator_id=seed["user_id"],
            n_active=2,
            n_cancelled=0,
        )
        # Owner already holds 10 on (strategy, NIFTY, buy).
        owner_id = await _make_position(
            db_session_maker,
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            credential_id=seed["credential_id"],
            symbol="NIFTY",
            side="buy",
            qty=10,
            subscription_id=None,
        )
        sig = await _seed_signal(
            db_session_maker,
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            symbol="NIFTY",
            action="BUY",
            side="long",
        )
        strategy = await _load_strategy(db_session_maker, seed["strategy_id"])

        # Dispatch TWICE (a re-entry) — each subscriber must sum only within its
        # OWN scope; the owner must be untouched.
        for _ in range(2):
            async with db_session_maker() as s:
                await dispatch_subscriber_executions(
                    signal=sig, strategy=strategy, subscribers=refs, db=s
                )

        rows = await _positions(
            db_session_maker, strategy_id=seed["strategy_id"], symbol="NIFTY", side="buy"
        )
        return owner_id, refs, rows

    owner_id, refs, rows = _run(_inner())

    by_scope = {r.subscription_id: r for r in rows}
    # Three fully isolated positions: owner (NULL) + one per subscriber.
    assert len(rows) == 3
    assert set(by_scope) == {None, refs[0].subscription_id, refs[1].subscription_id}

    # Owner is UNCHANGED — no subscriber quantity bled in.
    owner_row = by_scope[None]
    assert owner_row.id == owner_id
    assert owner_row.remaining_quantity == 10
    assert owner_row.total_quantity == 10

    # Each subscriber summed only within its own scope: 1 (entry_lots) x 2 dispatches.
    for ref in refs:
        sub_row = by_scope[ref.subscription_id]
        assert sub_row.remaining_quantity == 2
        assert sub_row.total_quantity == 2


# ═══════════════════════════════════════════════════════════════════════
# PAPER ONLY — zero real-broker calls even when the strategy is LIVE
# ═══════════════════════════════════════════════════════════════════════


def test_dispatch_zero_real_broker_even_when_strategy_live(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    monkeypatch: Any,
) -> None:
    import app.services.strategy_executor as se

    live_calls: list[int] = []
    monkeypatch.setattr(
        se, "place_strategy_orders", lambda *a, **k: live_calls.append(1)
    )

    async def _inner() -> tuple[list[Any], list[StrategyPosition], bool]:
        refs = await _seed_listing_and_subs(
            db_session_maker,
            strategy_id=seed["strategy_id"],
            creator_id=seed["user_id"],
            n_active=2,
            n_cancelled=0,
        )
        # Flip the strategy LIVE — subscribers must STILL be paper.
        async with db_session_maker() as s:
            strat = await s.get(Strategy, seed["strategy_id"])
            strat.is_paper = False
            await s.commit()

        sig = await _seed_signal(
            db_session_maker,
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            symbol="NIFTY",
            action="BUY",
            side="long",
        )
        strategy = await _load_strategy(db_session_maker, seed["strategy_id"])
        is_live = strategy.is_paper is False

        async with db_session_maker() as s:
            results = await dispatch_subscriber_executions(
                signal=sig, strategy=strategy, subscribers=refs, db=s
            )

        rows = await _positions(db_session_maker, strategy_id=seed["strategy_id"])
        return results, rows, is_live

    results, rows, is_live = _run(_inner())

    assert is_live, "strategy must be LIVE for this test to be meaningful"
    assert live_calls == [], "zero live-order entry calls even when strategy is LIVE"
    assert all(r.paper is True for r in results)
    assert all(r.broker_order_id and r.broker_order_id.startswith("PAPER-") for r in results)
    # Two ISOLATED paper positions were still created (all subscriber-scoped).
    sub_rows = [r for r in rows if r.subscription_id is not None]
    assert len(sub_rows) == 2


# ═══════════════════════════════════════════════════════════════════════
# Per-subscriber size — lots_override gives different-sized isolated positions
# ═══════════════════════════════════════════════════════════════════════


def test_lots_override_gives_different_sized_isolated_positions(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
) -> None:
    async def _inner() -> tuple[uuid.UUID, list[SubscriberRef], list[StrategyPosition]]:
        # Owner already holds 10 on (strategy, NIFTY, buy) — must stay untouched.
        owner_id = await _make_position(
            db_session_maker,
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            credential_id=seed["credential_id"],
            symbol="NIFTY",
            side="buy",
            qty=10,
            subscription_id=None,
        )
        # Two subscribers with DIFFERENT lots_override.
        refs = await _seed_listing_and_subs(
            db_session_maker,
            strategy_id=seed["strategy_id"],
            creator_id=seed["user_id"],
            n_active=2,
            n_cancelled=0,
            lots_overrides=[2, 5],
        )
        sig = await _seed_signal(
            db_session_maker,
            user_id=seed["user_id"],
            strategy_id=seed["strategy_id"],
            symbol="NIFTY",
            action="BUY",
            side="long",
        )
        strategy = await _load_strategy(db_session_maker, seed["strategy_id"])
        async with db_session_maker() as s:
            await dispatch_subscriber_executions(
                signal=sig, strategy=strategy, subscribers=refs, db=s
            )
        rows = await _positions(
            db_session_maker, strategy_id=seed["strategy_id"], symbol="NIFTY", side="buy"
        )
        return owner_id, refs, rows

    owner_id, refs, rows = _run(_inner())
    by_scope = {r.subscription_id: r for r in rows}

    # Three isolated rows; owner UNCHANGED (no subscriber size bled in).
    assert len(rows) == 3
    assert by_scope[None].id == owner_id
    assert by_scope[None].remaining_quantity == 10

    # Each subscriber sized by its OWN lots_override (paper lot_size 1).
    assert by_scope[refs[0].subscription_id].remaining_quantity == 2
    assert by_scope[refs[1].subscription_id].remaining_quantity == 5


# ═══════════════════════════════════════════════════════════════════════
# Per-subscriber credential resolution (machinery only — never used)
# ═══════════════════════════════════════════════════════════════════════


async def _make_cred(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    active: bool = True,
) -> uuid.UUID:
    async with maker() as s:
        cred = BrokerCredential(
            user_id=user_id,
            broker_name=BrokerName.DHAN,
            client_id_enc=encrypt_credential("CID"),
            api_key_enc=encrypt_credential("KEY"),
            api_secret_enc=encrypt_credential("SEC"),
            access_token_enc=encrypt_credential("TOK"),
            is_active=active,
        )
        s.add(cred)
        await s.commit()
        return cred.id


def test_resolve_subscriber_credential_explicit_fallback_missing(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    monkeypatch: Any,
) -> None:
    import app.services.strategy_executor as se

    # If resolution ever routed through the live order entry, this would record.
    live_calls: list[int] = []
    monkeypatch.setattr(
        se, "place_strategy_orders", lambda *a, **k: live_calls.append(1)
    )

    async def _inner() -> tuple[uuid.UUID, uuid.UUID, Any, Any, Any]:
        refs = await _seed_listing_and_subs(
            db_session_maker,
            strategy_id=seed["strategy_id"],
            creator_id=seed["user_id"],
            n_active=3,
            n_cancelled=0,
        )
        a, b, c = refs
        # A: explicit, valid cred of its own.
        a_cred = await _make_cred(db_session_maker, user_id=a.subscriber_id)
        a_explicit = replace(a, broker_credential_id=a_cred)
        # B: no explicit, but HAS an active cred -> fallback.
        b_cred = await _make_cred(db_session_maker, user_id=b.subscriber_id)
        # C: no credential at all -> missing.
        async with db_session_maker() as s:
            res_a = await resolve_subscriber_credential(a_explicit, s)
            res_b = await resolve_subscriber_credential(b, s)
            res_c = await resolve_subscriber_credential(c, s)
        return a_cred, b_cred, res_a, res_b, res_c

    a_cred, b_cred, res_a, res_b, res_c = _run(_inner())

    # Explicit chosen credential.
    assert res_a.usable is True
    assert res_a.source == "explicit"
    assert res_a.credential_id == a_cred
    # Fallback to the subscriber's active credential.
    assert res_b.usable is True
    assert res_b.source == "fallback"
    assert res_b.credential_id == b_cred
    # Missing — flagged, no credential.
    assert res_c.usable is False
    assert res_c.source == "none"
    assert res_c.credential_id is None

    # Resolution is pure machinery — it NEVER places a real order.
    assert live_calls == []
