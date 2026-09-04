"""Ledger payload re-point (docs/LEDGER_PAYLOAD_PROPOSAL.md §3) — live strategies.

A LIVE listing's numbers come from the P&L reconciler over the strategy's
CLOSED positions priced from REAL fills; only COMPLETE trips count; the P&L
is NET of modelled charges and says so (``pnl_basis``); the unpriced count
rides on the chain; nothing is ever published as a zero.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.roles import ROLE_CREATOR
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential, BrokerName
from app.db.models.ledger_snapshot import LedgerSnapshot
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.strategy_engine.ledger.snapshots import (
    PNL_BASIS_RECONCILED_NET,
    NothingToPublishError,
    build_snapshot_preview,
    create_daily_snapshot,
)
from app.strategy_engine.ledger.verification import verify_listing_chain


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-ledger-live-{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


def _dhan(status: str, price: float | None, qty: int | None, order_id: str) -> dict[str, Any]:
    # Same shape the executor writes for a Dhan fill (see tests/test_pnl_reconciler.py::_dhan_fill).
    raw: dict[str, Any] = {"orderId": order_id, "orderStatus": status}
    if price is not None:
        raw["price"] = price
    if qty is not None:
        raw["filledQty"] = qty
    return {"raw": raw, "status": "pending", "broker_order_id": order_id}


async def _seed_live_listing(db: AsyncSession) -> tuple[MarketplaceListing, Strategy, User]:
    creator = User(
        email=f"c-{uuid.uuid4().hex[:8]}@x", password_hash="x", is_active=True, role=ROLE_CREATOR
    )
    db.add(creator)
    await db.flush()
    strategy = Strategy(user_id=creator.id, name="BSE live", is_paper=False)
    db.add(strategy)
    await db.flush()
    cred = BrokerCredential(
        user_id=creator.id,
        broker_name=BrokerName.DHAN,
        client_id_enc="x",
        api_key_enc="x",
        api_secret_enc="x",
        is_active=True,
    )
    db.add(cred)
    await db.flush()
    strategy.broker_credential_id = cred.id
    await db.flush()
    listing = MarketplaceListing(
        strategy_id=strategy.id,
        creator_id=creator.id,
        title="Strategy S1",
        description="d",
        price_inr=Decimal("0"),
        tags=[],
        status="published",
        published_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing, strategy, creator


async def _round_trip(
    db: AsyncSession,
    strategy: Strategy,
    user: User,
    *,
    side: str,
    qty: int,
    entry: float,
    exit_: float,
    closed_at: datetime,
    exit_role: str = "direct_sl",
    complete: bool = True,
) -> StrategyPosition:
    """One CLOSED position with a real entry fill and (optionally) a real exit fill."""
    entry_sig = StrategySignal(
        strategy_id=strategy.id, user_id=user.id, symbol="BSE-FUT", action="ENTRY", raw_payload={}
    )
    exit_sig = StrategySignal(
        strategy_id=strategy.id, user_id=user.id, symbol="BSE-FUT", action="EXIT", raw_payload={}
    )
    db.add_all([entry_sig, exit_sig])
    await db.flush()
    exit_side = "sell" if side == "buy" else "buy"
    db.add(
        StrategyExecution(
            signal_id=entry_sig.id,
            broker_credential_id=strategy.broker_credential_id,
            broker_order_id=f"e-{entry_sig.id}",
            leg_number=1,
            leg_role="entry",
            symbol="BSE-FUT",
            side=side,
            quantity=qty,
            order_type="MARKET",
            broker_response=_dhan("TRADED", entry, qty, f"e-{entry_sig.id}"),
        )
    )
    history = [
        {
            "action": "entry",
            "leg_role": "entry",
            "qty": qty,
            "side": side,
            "signal_id": str(entry_sig.id),
        }
    ]
    if complete:
        db.add(
            StrategyExecution(
                signal_id=exit_sig.id,
                broker_credential_id=strategy.broker_credential_id,
                broker_order_id=f"x-{exit_sig.id}",
                leg_number=1,
                leg_role=exit_role,
                symbol="BSE-FUT",
                side=exit_side,
                quantity=qty,
                order_type="MARKET",
                broker_response=_dhan("TRADED", exit_, qty, f"x-{exit_sig.id}"),
            )
        )
        history.append(
            {
                "action": exit_role,
                "leg_role": exit_role,
                "qty": qty,
                "side": exit_side,
                "signal_id": str(exit_sig.id),
            }
        )
    pos = StrategyPosition(
        user_id=user.id,
        strategy_id=strategy.id,
        broker_credential_id=strategy.broker_credential_id,
        signal_id=entry_sig.id,
        symbol="BSE-FUT",
        side=side,
        total_quantity=qty,
        remaining_quantity=0,
        avg_entry_price=Decimal(str(entry)),
        status="closed",
        opened_at=closed_at - timedelta(days=1),
        closed_at=closed_at,
        action_history=history,
    )
    db.add(pos)
    await db.commit()
    return pos


# ─── Refuse, never a zero ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_live_listing_with_no_closed_position_refuses(db: AsyncSession) -> None:
    listing, _s, _u = await _seed_live_listing(db)
    with pytest.raises(NothingToPublishError):
        await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))
    assert (await db.execute(select(LedgerSnapshot))).scalars().all() == []


@pytest.mark.asyncio
async def test_live_listing_with_only_unpriced_positions_refuses(db: AsyncSession) -> None:
    """Closed positions exist but none can be priced (exit taken off-platform) → nothing published."""
    listing, strategy, user = await _seed_live_listing(db)
    await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=4000,
        exit_=0,
        closed_at=datetime(2026, 6, 5, tzinfo=UTC),
        complete=False,
    )
    with pytest.raises(NothingToPublishError) as exc:
        await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))
    assert "0 complete" in str(exc.value)
    assert (await db.execute(select(LedgerSnapshot))).scalars().all() == []


# ─── Real numbers: net of modelled charges, coverage on the chain ─────


@pytest.mark.asyncio
async def test_live_payload_is_net_of_estimated_costs_and_carries_unpriced(
    db: AsyncSession,
) -> None:
    listing, strategy, user = await _seed_live_listing(db)
    # BSE Jun-12 trip from the reconciler's pinned fixture: long 750 @ 4014.80 → 4035.00
    win = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=4014.80,
        exit_=4035.00,
        closed_at=datetime(2026, 6, 15, tzinfo=UTC),
    )
    loss = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=4212.00,
        exit_=4105.20,
        closed_at=datetime(2026, 6, 16, tzinfo=UTC),
    )
    _unpriced = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=400,
        entry=3555.20,
        exit_=0,
        closed_at=datetime(2026, 8, 12, tzinfo=UTC),
        complete=False,
    )

    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))

    gross_win = Decimal("750") * (Decimal("4035.00") - Decimal("4014.80"))
    gross_loss = Decimal("750") * (Decimal("4105.20") - Decimal("4212.00"))
    assert snap.live_trades_count == 2
    assert snap.total_trades == 2  # paper sessions never summed into a live record
    assert snap.paper_trades_count == 0
    assert snap.unpriced_positions == 1
    assert snap.pnl_basis == PNL_BASIS_RECONCILED_NET
    # NET is strictly below gross (costs are positive), and only priced trips are summed.
    assert snap.cumulative_pnl_inr < gross_win + gross_loss
    assert snap.cumulative_pnl_inr > gross_win + gross_loss - Decimal("5000")
    assert snap.win_rate == Decimal("0.5000")
    # Drawdown: peak after the win, trough after the loss.
    assert snap.max_drawdown_pct > Decimal("100")  # the loss wipes more than the win
    assert win.final_pnl is None and loss.final_pnl is None  # the ledger never writes final_pnl


@pytest.mark.asyncio
async def test_never_reads_final_pnl_recomputes_from_fills(db: AsyncSession) -> None:
    """A stored final_pnl (even a zero) does not enter the payload — fills do."""
    listing, strategy, user = await _seed_live_listing(db)
    pos = await _round_trip(
        db,
        strategy,
        user,
        side="sell",
        qty=400,
        entry=3300.00,
        exit_=3250.00,
        closed_at=datetime(2026, 8, 24, tzinfo=UTC),
    )
    pos.final_pnl = Decimal("0")  # a stored zero — must be ignored
    await db.commit()
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))
    assert snap.cumulative_pnl_inr > Decimal("15000")  # 400 x 50 = 20,000 gross minus costs


# ─── Dry run + verification ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_returns_payload_and_inserts_nothing(db: AsyncSession) -> None:
    listing, strategy, user = await _seed_live_listing(db)
    await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=4014.80,
        exit_=4035.00,
        closed_at=datetime(2026, 6, 15, tzinfo=UTC),
    )
    preview = await build_snapshot_preview(db, listing.id, snapshot_date=date(2026, 9, 4))
    assert preview.sequence_number == 1
    assert preview.live_trades_count == 1
    assert preview.pnl_basis == PNL_BASIS_RECONCILED_NET
    assert (await db.execute(select(LedgerSnapshot))).scalars().all() == []
    # And the real snapshot hashes exactly the previewed payload.
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))
    assert Decimal(preview.cumulative_pnl_inr) == snap.cumulative_pnl_inr


@pytest.mark.asyncio
async def test_new_fields_are_in_the_hash_and_the_chain_verifies(db: AsyncSession) -> None:
    listing, strategy, user = await _seed_live_listing(db)
    await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=4014.80,
        exit_=4035.00,
        closed_at=datetime(2026, 6, 15, tzinfo=UTC),
    )
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))
    result = await verify_listing_chain(db, listing.id)
    assert result.is_chain_valid is True
    # Tampering with the coverage count breaks the hash — it IS on the chain.
    snap.unpriced_positions = 99
    await db.commit()
    tampered = await verify_listing_chain(db, listing.id)
    assert tampered.is_chain_valid is False


# ─── Beat: scheduled, dormant ─────────────────────────────────────────


def test_daily_snapshot_beat_is_scheduled_after_close_and_flag_defaults_off() -> None:
    from app.core.config import Settings
    from app.tasks.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["ledger-daily-snapshot"]
    assert entry["task"] == "app.tasks.ledger_snapshot_tasks.take_daily_snapshots"
    sched = entry["schedule"]
    assert sched.hour == {10} and sched.minute == {45}  # 16:15 IST
    assert Settings.model_fields["ledger_daily_snapshot_enabled"].default is False


def test_take_daily_snapshots_is_dormant_while_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.tasks.ledger_snapshot_tasks as mod

    calls: list[str] = []
    monkeypatch.setattr(mod, "_run", lambda coro: __import__("asyncio").run(coro))
    import app.core.config as cfg

    monkeypatch.setattr(
        cfg, "get_settings", lambda: SimpleNamespace(ledger_daily_snapshot_enabled=False)
    )
    import app.db.session as sess

    monkeypatch.setattr(sess, "get_sessionmaker", lambda: calls.append("sessionmaker") or None)
    out = mod.take_daily_snapshots()
    assert out == {"status": "dormant", "listings": 0, "created": 0, "skipped": 0}
    assert calls == []  # never even opened a session
