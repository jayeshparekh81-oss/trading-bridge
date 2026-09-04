"""Ledger payload re-point (docs/LEDGER_PAYLOAD_PROPOSAL.md §3) — live strategies.

A LIVE listing's numbers are the RECORD: ``final_pnl`` as written by the
P&L reconciler under the founder's exit rule (2026-09-04, cutover-26) —
priced from the ACCOUNT's real fills, NET of modelled charges — together
with its ``pnl_attribution`` tag. Only positions carrying a value AND a
priced tag (``bot_only`` / ``account_flat``) count; the unpriced count and
its human-interfered subset ride on the chain; nothing is ever published
as a zero. The ledger never re-reconciles live: that path sees only the
bot's own orders and would republish a number the founder ruled
unattributable.
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
from app.db.models.ledger_attestation import LedgerAttestation
from app.db.models.ledger_snapshot import LedgerSnapshot
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.domains.pnl_reconciler.attribution import (
    TAG_ACCOUNT_FLAT,
    TAG_BOT_ONLY,
    TAG_HUMAN_INTERFERED,
    TAG_UNPRICEABLE,
)
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
    # Same shape the executor writes for a Dhan fill (see tests/test_pnl_reconciler.py::_dhan_fill):
    # the fill is ``averageTradedPrice``; ``price`` is the order's limit (a decoy here).
    raw: dict[str, Any] = {
        "orderId": order_id,
        "orderStatus": status,
        "correlationId": "strategy-engine",
    }
    if price is not None:
        raw["averageTradedPrice"] = price
        raw["price"] = round(price + 40.0, 2)
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
    final_pnl: Decimal | None = None,
    attribution: str | None = None,
) -> StrategyPosition:
    """One CLOSED position with a real entry fill and (optionally) a real exit fill.

    ``final_pnl`` / ``attribution`` are what the reconciler's write path
    stamps under the founder's exit rule; ``complete`` positions default to a
    ``bot_only`` NET value (gross minus a flat 800 of modelled charges), an
    incomplete one to NULL + ``human_interfered``.
    """
    if complete and final_pnl is None:
        sign = Decimal(1) if side == "buy" else Decimal(-1)
        final_pnl = sign * Decimal(qty) * (Decimal(str(exit_)) - Decimal(str(entry))) - Decimal(
            "800"
        )
    if attribution is None:
        attribution = TAG_BOT_ONLY if complete else TAG_HUMAN_INTERFERED
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
        final_pnl=final_pnl,
        pnl_attribution=attribution,
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
    assert "0 priced" in str(exc.value) and "1 human-interfered" in str(exc.value)
    assert "1 unpriced trades" in str(exc.value)
    assert (await db.execute(select(LedgerSnapshot))).scalars().all() == []


# ─── Real numbers: net of modelled charges, coverage on the chain ─────


@pytest.mark.asyncio
async def test_live_payload_is_net_of_estimated_costs_and_carries_unpriced(
    db: AsyncSession,
) -> None:
    listing, strategy, user = await _seed_live_listing(db)
    # Real BSE record under the founder's rule (2026-09-04), as the reconciler
    # wrote it: 388c845e closed by the founder's manual flat fill (+454.56 net,
    # account_flat); cc159c97 bot-only (-21,493.17 net); 844b8037 entered on
    # top of a prior manual lot → human-interfered, NULL; a phantom row → unpriceable.
    win = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=800,
        entry=3397.525,
        exit_=3400.075,
        closed_at=datetime(2026, 8, 28, tzinfo=UTC),
        final_pnl=Decimal("454.56"),
        attribution=TAG_ACCOUNT_FLAT,
    )
    loss = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=4170.00,
        exit_=4143.75,
        closed_at=datetime(2026, 6, 16, tzinfo=UTC),
        final_pnl=Decimal("-21493.17"),
        attribution=TAG_BOT_ONLY,
    )
    _interfered = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=800,
        entry=3270.00,
        exit_=0,
        closed_at=datetime(2026, 9, 4, tzinfo=UTC),
        complete=False,
        attribution=TAG_HUMAN_INTERFERED,
    )
    _phantom = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=2,
        entry=0,
        exit_=0,
        closed_at=datetime(2026, 5, 24, tzinfo=UTC),
        complete=False,
        attribution=TAG_UNPRICEABLE,
    )

    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))

    assert snap.live_trades_count == 2
    assert snap.total_trades == 2  # paper sessions never summed into a live record
    assert snap.paper_trades_count == 0
    # the phantom (unpriceable) row was never a trade: not counted at all, so
    # every unpriced position on the chain is explained
    assert snap.unpriced_positions == 1
    assert snap.human_interfered_positions == 1  # explained on the chain, not silent
    assert snap.pnl_basis == PNL_BASIS_RECONCILED_NET
    # The record is the basis: the stored NETs, summed, nothing recomputed.
    assert snap.cumulative_pnl_inr == Decimal("454.56") + Decimal("-21493.17")
    assert snap.win_rate == Decimal("0.5000")
    # Drawdown in RUPEES, temporal order (loss in June, win in August):
    # series -21,493.17 → -21,038.61; peak 0 → trough -21,493.17.
    assert snap.max_drawdown_pct is None
    assert snap.max_drawdown_inr == Decimal("21493.17")
    # The ledger never writes final_pnl — the stored record is untouched.
    assert win.final_pnl == Decimal("454.56") and loss.final_pnl == Decimal("-21493.17")


@pytest.mark.asyncio
async def test_a_value_without_a_priced_attribution_tag_is_never_published(
    db: AsyncSession,
) -> None:
    """A stored final_pnl only counts with a priced tag. A value written before
    the rule existed (tag NULL), or a value on a human-interfered row, is
    unpriced — and the ledger NEVER re-reconciles from the bot's own fills
    to fill the gap (that path cannot see the founder's manual book)."""
    listing, strategy, user = await _seed_live_listing(db)
    untagged = await _round_trip(
        db,
        strategy,
        user,
        side="sell",
        qty=400,
        entry=3300.00,
        exit_=3250.00,
        closed_at=datetime(2026, 8, 24, tzinfo=UTC),
        final_pnl=Decimal("19000"),
        attribution=None,
    )
    untagged.pnl_attribution = None  # pre-rule value, no tag
    stale = await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=3975.00,
        exit_=4117.60,
        closed_at=datetime(2026, 6, 15, tzinfo=UTC),
        final_pnl=Decimal("14283.35"),  # the old wrong value, never NULLed
        attribution=TAG_HUMAN_INTERFERED,
    )
    await db.commit()
    with pytest.raises(NothingToPublishError) as exc:
        await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))
    assert "0 priced" in str(exc.value) and "1 human-interfered" in str(exc.value)
    assert untagged.final_pnl == Decimal("19000") and stale.final_pnl == Decimal("14283.35")


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
    assert preview.max_drawdown_pct is None and preview.max_drawdown_inr is not None
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
    assert snap.human_interfered_positions == 0
    result = await verify_listing_chain(db, listing.id)
    assert result.is_chain_valid is True
    # Tampering with the coverage count breaks the hash — it IS on the chain.
    snap.unpriced_positions = 99
    await db.commit()
    tampered = await verify_listing_chain(db, listing.id)
    assert tampered.is_chain_valid is False
    # ...and so does the human-interfered count (046): the explanation is chained too.
    snap.unpriced_positions = 0
    snap.human_interfered_positions = 7
    await db.commit()
    tampered_again = await verify_listing_chain(db, listing.id)
    assert tampered_again.is_chain_valid is False


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


@pytest.mark.asyncio
async def test_real_bse_shaped_series_does_not_overflow_the_percent_column(
    db: AsyncSession,
) -> None:
    """The verifier's catch: +14k then -330k would be a 2,411% 'drawdown of the
    peak' — the live payload publishes rupees instead and inserts cleanly."""
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
        final_pnl=Decimal("14283.35"),
    )
    await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=750,
        entry=4212.00,
        exit_=3800.00,
        closed_at=datetime(2026, 6, 16, tzinfo=UTC),
        final_pnl=Decimal("-309860.87"),
    )
    await _round_trip(
        db,
        strategy,
        user,
        side="buy",
        qty=800,
        entry=3429.00,
        exit_=3300.00,
        closed_at=datetime(2026, 8, 31, tzinfo=UTC),
        final_pnl=Decimal("-103948.34"),
    )
    snap = await create_daily_snapshot(db, listing.id, snapshot_date=date(2026, 9, 4))
    assert snap.max_drawdown_pct is None
    assert snap.max_drawdown_inr > Decimal("400000")
    assert snap.cumulative_pnl_inr < Decimal("-390000")


@pytest.mark.asyncio
async def test_pre_045_row_without_pnl_basis_still_verifies(db: AsyncSession) -> None:
    """A row hashed before the 045 keys existed verifies: the verifier omits
    the three keys when pnl_basis is NULL."""
    from app.strategy_engine.ledger.hashing import chain_signature_for, data_hash_for

    listing, _s, _u = await _seed_live_listing(db)
    legacy = {
        "listing_id": str(listing.id),
        "snapshot_date": "2026-05-01",
        "sequence_number": 1,
        "cumulative_pnl_inr": "70.0000",
        "max_drawdown_pct": "30.0000",
        "total_trades": 6,
        "win_rate": "0.5000",
        "sharpe_ratio": None,
        "days_since_publish": 5,
        "paper_trades_count": 6,
        "live_trades_count": 0,
    }
    dh = data_hash_for(legacy)
    db.add(
        LedgerSnapshot(
            listing_id=listing.id,
            snapshot_date=date(2026, 5, 1),
            sequence_number=1,
            cumulative_pnl_inr=Decimal("70"),
            max_drawdown_pct=Decimal("30"),
            total_trades=6,
            win_rate=Decimal("0.5"),
            sharpe_ratio=None,
            days_since_publish=5,
            paper_trades_count=6,
            live_trades_count=0,
            unpriced_positions=None,
            pnl_basis=None,
            max_drawdown_inr=None,
            data_hash=dh,
            prior_hash=None,
            chain_signature=chain_signature_for(data_hash=dh, prior_hash=None),
            created_at=datetime.now(UTC),
        )
    )
    await db.flush()
    row = (
        await db.execute(select(LedgerSnapshot).where(LedgerSnapshot.listing_id == listing.id))
    ).scalar_one()
    db.add(
        LedgerAttestation(
            snapshot_id=row.id,
            attestation_type="daily_snapshot",
            attestation_hash=data_hash_for({"chain_signature": row.chain_signature}),
            polygon_tx_hash=None,
            attested_at=datetime.now(UTC),
        )
    )
    await db.commit()
    result = await verify_listing_chain(db, listing.id)
    assert result.is_chain_valid is True, result.first_break_reason
