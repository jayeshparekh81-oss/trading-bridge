"""Marketplace Module 2 — flag-gated, PAPER-ONLY subscriber dispatch in webhook.

Proves, against the real (sqlite) DB + the live webhook handler:

    (a) Flag OFF (default) — the fan-out block never runs:
        ``dispatch_subscriber_executions`` is never called and ``dispatch_signal``
        fires exactly once (owner). Owner 1->1 path is unchanged.
    (b) Flag ON + seeded active subscriptions — one PAPER simulated fill runs
        per ACTIVE subscriber (``_simulate_fill`` called N times), the owner
        still dispatches exactly once, NO real-broker / live-order entry is
        called, and NO position rows are written.
    (c) ``resolve_active_subscriptions`` is read-only — active-only rows, no
        INSERT/UPDATE/DELETE (covered alongside M1).

Uses the shared ``tests/integration/conftest.py`` harness (paper mode forced,
fake Redis, Celery eager, HMAC). The owner ``dispatch_signal`` is mocked to a
no-op spy in (a)/(b) so the eager worker never runs — that isolates the
webhook fast path and lets us assert what the fan-out adds (and does not).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.strategy_position import StrategyPosition
from app.db.models.user import User
from app.services.marketplace_fanout import resolve_active_subscriptions
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
    """Set MARKETPLACE_FANOUT_ENABLED deterministically and rebuild settings.

    Mirrors how the ``client`` fixture flips STRATEGY_PAPER_MODE — the webhook
    reads ``get_settings()`` per request, so clearing the lru_cache makes the
    next request observe the new value.
    """
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
) -> list[uuid.UUID]:
    """Publish a listing for ``strategy_id`` + N active and M cancelled subs.

    Returns the active subscription ids. Each subscriber is its own bare User
    row (FK-valid) so the active-vs-cancelled filter is exercised honestly.
    """
    active_ids: list[uuid.UUID] = []
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
            sub = MarketplaceSubscription(
                listing_id=listing.id,
                subscriber_id=u.id,
                subscribed_at=datetime.now(UTC),
                status="active",
                amount_paid_inr=Decimal("0"),
            )
            s.add(sub)
            await s.flush()
            active_ids.append(sub.id)

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
    return active_ids


# ═══════════════════════════════════════════════════════════════════════
# (c) resolve_active_subscriptions — active-only + read-only
# ═══════════════════════════════════════════════════════════════════════


def test_resolve_returns_active_only_and_is_read_only(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
) -> None:
    async def _run_inner() -> tuple[list[Any], int, int, tuple[set, set, set]]:
        await _seed_listing_and_subs(
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
        return result, before, after, pending

    result, before, after, pending = _run(_run_inner())

    # active-only: 2 active returned, the cancelled row excluded
    assert len(result) == 2
    assert all(r.status == "active" for r in result)

    # read-only: row count unchanged + nothing pending on the session
    assert before == 3  # 2 active + 1 cancelled seeded
    assert after == 3
    assert pending == (set(), set(), set())


# ═══════════════════════════════════════════════════════════════════════
# (a) Flag OFF — fan-out block never runs, owner path unchanged
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
# (b) Flag ON — one PAPER fill per subscriber; no live order, no positions
# ═══════════════════════════════════════════════════════════════════════


def test_flag_on_runs_paper_fill_per_subscriber_no_live_no_positions(
    client: Any,
    seed: dict[str, Any],
    db_session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    _force_flag(monkeypatch, True)

    # Owner dispatch -> no-op spy so the eager worker never runs. This both
    # isolates the fast path AND lets us prove the fan-out adds no dispatch.
    dispatched: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.api.strategy_webhook.dispatch_signal",
        lambda sid, kind: dispatched.append((sid, kind)),
    )

    import app.services.strategy_executor as se

    # Count subscriber PAPER fills (one per active subscriber) by spying on the
    # SHARED paper-fill primitive the owner path uses.
    sim_calls: list[Any] = []
    real_sim = se._simulate_fill

    def _sim_spy(signal: Any, quantity: int) -> Any:
        sim_calls.append((signal, quantity))
        return real_sim(signal, quantity)

    monkeypatch.setattr(se, "_simulate_fill", _sim_spy)

    # The live execution entry must NEVER be reached for subscribers.
    live_calls: list[int] = []
    monkeypatch.setattr(
        se, "place_strategy_orders", lambda *a, **k: live_calls.append(1)
    )

    _run(
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

    # Owner dispatched exactly once; the fan-out added NO dispatch.
    assert len(dispatched) == 1, f"fan-out must not dispatch; got {dispatched}"

    # Exactly one PAPER fill per ACTIVE subscriber (cancelled excluded).
    assert len(sim_calls) == 2, f"expected 2 paper fills, got {len(sim_calls)}"

    # PAPER ONLY: the live/real execution entry was never called.
    assert live_calls == [], "subscribers must never hit the live execution entry"

    # No position rows written by the paper fan-out (owner worker mocked out).
    pos_count = _run(_count_positions(db_session_maker))
    assert pos_count == 0, "paper fan-out must not create positions"


async def _count_positions(maker: async_sessionmaker[AsyncSession]) -> int:
    async with maker() as s:
        return (
            await s.execute(select(func.count()).select_from(StrategyPosition))
        ).scalar_one()
