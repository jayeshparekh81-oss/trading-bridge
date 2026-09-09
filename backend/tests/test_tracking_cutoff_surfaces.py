"""The cut-off actually bites on the surfaces that count and sum money.

Three test files disable the epoch for their own cases — they are about marker
maths, the API contract and the hash chain, not about the boundary, and their
fixtures are dated months before it. That is legitimate, but it leaves a hole:
if the filter silently stopped working, those files would go on passing.

This file is the other half. It seeds one pre-cut row and one post-cut row on
each money surface and asserts the boundary counts exactly one of them.

The reporting-side complement to
``tests/integration/test_tracking_epoch_isolation.py``, which proves the same
constant never reaches the execution path.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.tracking_epoch import (
    markers_in_record,
    positions_in_record,
    tracking_epoch,
)
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.trade_marker import MarkerMode, MarkerSide, TradeMarker
from app.db.models.user import User
from app.schemas.broker import BrokerName


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Same in-memory harness the sibling suites use."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


def _epoch() -> datetime:
    e = tracking_epoch()
    assert e is not None, "these tests are meaningless with no cut-off set"
    return e.astimezone(UTC)


BEFORE = _epoch() - timedelta(days=45)
AFTER = _epoch() + timedelta(days=8)  # the founder's live row is 2026-09-08


async def _user_and_strategy(
    db: AsyncSession,
) -> tuple[User, Strategy, BrokerCredential]:
    user = User(
        email=f"cutoff-{uuid.uuid4().hex[:8]}@x", password_hash="x", is_active=True
    )
    db.add(user)
    await db.flush()
    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc="x",
        api_key_enc="x",
        api_secret_enc="x",
        is_active=True,
    )
    db.add(cred)
    await db.flush()
    strategy = Strategy(user_id=user.id, name="BSE live", is_paper=False)
    db.add(strategy)
    await db.flush()
    return user, strategy, cred


class TestPositionsAreScopedToTheRecord:
    async def test_only_the_post_cut_position_is_counted(
        self, db: AsyncSession
    ) -> None:
        """🔴 The boundary. One row each side; exactly one survives."""
        user, strategy, cred = await _user_and_strategy(db)
        for opened, qty in ((BEFORE, 750), (AFTER, 400)):
            db.add(
                StrategyPosition(
                    user_id=user.id,
                    strategy_id=strategy.id,
                    broker_credential_id=cred.id,
                    signal_id=None,
                    symbol="BSE-SEP2026-FUT",
                    side="buy",
                    total_quantity=qty,
                    remaining_quantity=0,
                    avg_entry_price=Decimal("3000"),
                    status="closed",
                    opened_at=opened,
                    closed_at=opened + timedelta(hours=6),
                    final_pnl=Decimal("1000"),
                )
            )
        await db.flush()

        in_record = (
            await db.execute(
                select(StrategyPosition).where(
                    StrategyPosition.user_id == user.id, positions_in_record()
                )
            )
        ).scalars().all()

        assert [p.total_quantity for p in in_record] == [400], (
            "the pre-cut position is still being counted"
        )

    async def test_the_archived_row_is_still_there_untouched(
        self, db: AsyncSession
    ) -> None:
        """🔴 ARCHIVED, NOT DELETED. The founder's standing rule: these are
        real broker orders held for tax and audit."""
        user, strategy, cred = await _user_and_strategy(db)
        db.add(
            StrategyPosition(
                user_id=user.id,
                strategy_id=strategy.id,
                broker_credential_id=cred.id,
                signal_id=None,
                symbol="BSE-JUN2026-FUT",
                side="buy",
                total_quantity=750,
                remaining_quantity=0,
                avg_entry_price=Decimal("4116.90"),
                status="closed",
                opened_at=BEFORE,
                closed_at=BEFORE + timedelta(days=1),
                final_pnl=Decimal("-198265.66"),
            )
        )
        await db.flush()

        # Hidden from the record...
        assert not (
            await db.execute(
                select(StrategyPosition).where(
                    StrategyPosition.user_id == user.id, positions_in_record()
                )
            )
        ).scalars().all()

        # ...and still present, with its money intact.
        archived = (
            await db.execute(
                select(StrategyPosition).where(StrategyPosition.user_id == user.id)
            )
        ).scalars().one()
        assert archived.final_pnl == Decimal("-198265.66")

    async def test_a_position_opened_exactly_on_the_epoch_is_in_the_record(
        self, db: AsyncSession
    ) -> None:
        """The boundary is inclusive: >= , not >. 1 Sep 00:00:00 IST counts."""
        user, strategy, cred = await _user_and_strategy(db)
        db.add(
            StrategyPosition(
                user_id=user.id,
                strategy_id=strategy.id,
                broker_credential_id=cred.id,
                signal_id=None,
                symbol="BSE-SEP2026-FUT",
                side="sell",
                total_quantity=400,
                remaining_quantity=400,
                avg_entry_price=Decimal("3300"),
                status="open",
                opened_at=_epoch(),
            )
        )
        await db.flush()
        rows = (
            await db.execute(
                select(StrategyPosition).where(
                    StrategyPosition.user_id == user.id, positions_in_record()
                )
            )
        ).scalars().all()
        assert len(rows) == 1


class TestMarkerSummaryIsScopedToTheRecord:
    async def test_only_post_cut_markers_are_summed(self, db: AsyncSession) -> None:
        """🔴 This summary was an UNBOUNDED sum of money before the cut-off —
        its list sibling already took from_ts/to_ts, this did not."""
        owner, strategy, _cred = await _user_and_strategy(db)
        for ts, pnl in ((BEFORE, Decimal("9999")), (AFTER, Decimal("250"))):
            db.add(
                TradeMarker(
                    user_id=owner.id,
                    strategy_id=strategy.id,
                    mode=MarkerMode.PAPER.value,
                    side=MarkerSide.LONG_EXIT.value,
                    symbol="BSE-SEP2026-FUT",
                    exchange="NFO",
                    price=Decimal("3300"),
                    quantity=400,
                    pnl=pnl,
                    timestamp_utc=ts,
                )
            )
        await db.flush()

        total = (
            await db.execute(
                select(func.coalesce(func.sum(TradeMarker.pnl), 0)).where(
                    TradeMarker.strategy_id == strategy.id, markers_in_record()
                )
            )
        ).scalar_one()
        assert Decimal(total) == Decimal("250"), (
            "the pre-cut marker is still in the money total"
        )


class TestTurningTheCutOffOffRestoresEverything:
    async def test_no_epoch_means_show_everything(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """🔴 REVERSIBLE BY CHANGING ONE VALUE. That claim is the whole reason
        this is a setting and not a column, so it gets a test."""
        user, strategy, cred = await _user_and_strategy(db)
        for opened in (BEFORE, AFTER):
            db.add(
                StrategyPosition(
                    user_id=user.id,
                    strategy_id=strategy.id,
                    broker_credential_id=cred.id,
                    signal_id=None,
                    symbol="BSE-SEP2026-FUT",
                    side="buy",
                    total_quantity=400,
                    remaining_quantity=0,
                    avg_entry_price=Decimal("3000"),
                    status="closed",
                    opened_at=opened,
                    closed_at=opened + timedelta(hours=6),
                )
            )
        await db.flush()

        scoped = select(StrategyPosition).where(
            StrategyPosition.user_id == user.id, positions_in_record()
        )
        assert len((await db.execute(scoped)).scalars().all()) == 1

        monkeypatch.setattr("app.core.tracking_epoch.tracking_epoch", lambda: None)
        both = select(StrategyPosition).where(
            StrategyPosition.user_id == user.id, positions_in_record()
        )
        assert len((await db.execute(both)).scalars().all()) == 2, (
            "clearing the epoch did not restore the archived row"
        )
