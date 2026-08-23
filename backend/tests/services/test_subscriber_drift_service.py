"""AUTO→MANUAL safety flip — subscriber_drift_service.

The safety property under test: a subscriber who closes a copied position
DIRECTLY at their broker is flipped from AUTO to MANUAL, so every further signal
for that trade becomes notification-only instead of firing an order.

The fail-safe matters as much as the flip: an unreachable broker is the ABSENCE
of evidence, not evidence of drift, and must never cost a customer their AUTO
mode.

Self-contained (in-memory aiosqlite). FK enforcement is off, so ids are plain
UUIDs and no User/Listing rows are required.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.services.subscriber_drift_service import (
    AUTO_MODE,
    DRIFT_FLIP_ACTION,
    MANUAL_MODE,
    check_and_flip_subscription,
)


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-drift-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


async def _seed_sub(maker, *, execution_mode: str = AUTO_MODE) -> uuid.UUID:
    async with maker() as s:
        sub = MarketplaceSubscription(
            listing_id=uuid.uuid4(),
            subscriber_id=uuid.uuid4(),
            subscribed_at=datetime.now(UTC),
            status="active",
            amount_paid_inr=Decimal("0"),
            execution_mode=execution_mode,
            is_paper=True,
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def _load(maker, sub_id) -> MarketplaceSubscription:
    async with maker() as s:
        return (
            await s.execute(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.id == sub_id
                )
            )
        ).scalar_one()


async def _audit_count(maker, sub_id) -> int:
    async with maker() as s:
        return (
            await s.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == str(sub_id))
            )
        ).scalar_one()


def _fetcher(value):
    async def _f(*, subscription, symbol):
        return value

    return _f


def _raising_fetcher(exc: Exception):
    async def _f(*, subscription, symbol):
        raise exc

    return _f


# ═══════════════════════════════════════════════════════════════════════
# DRIFT DETECTED → FLIPS
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_broker_flat_while_we_think_open_flips_to_manual(db_maker):
    """Customer closed the whole thing on Dhan → flip."""
    sub_id = await _seed_sub(db_maker)
    async with db_maker() as db:
        sub = (
            await db.execute(
                select(MarketplaceSubscription).where(
                    MarketplaceSubscription.id == sub_id
                )
            )
        ).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=2,
            fetch_broker_position=_fetcher(0),
        )

    assert decision.flipped is True
    assert decision.reason == "broker_flat"
    assert decision.drifted is True
    assert (await _load(db_maker, sub_id)).execution_mode == MANUAL_MODE


@pytest.mark.asyncio
async def test_broker_partial_close_flips_to_manual(db_maker):
    """Customer closed HALF on Dhan → still drift → flip."""
    sub_id = await _seed_sub(db_maker)
    async with db_maker() as db:
        sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=4,
            fetch_broker_position=_fetcher(2),
        )

    assert decision.flipped is True
    assert decision.reason == "broker_partial"
    assert decision.broker_quantity == 2
    assert decision.stored_quantity == 4
    assert (await _load(db_maker, sub_id)).execution_mode == MANUAL_MODE


@pytest.mark.asyncio
async def test_flip_writes_machine_readable_audit_row(db_maker):
    """Reason + timestamp land in audit_logs — no new column, no migration."""
    sub_id = await _seed_sub(db_maker)
    async with db_maker() as db:
        sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=2,
            fetch_broker_position=_fetcher(0),
        )

    assert decision.audit_log_id is not None
    async with db_maker() as s:
        row = (
            await s.execute(select(AuditLog).where(AuditLog.id == decision.audit_log_id))
        ).scalar_one()

    assert row.action == DRIFT_FLIP_ACTION
    assert row.resource_type == "marketplace_subscription"
    assert row.resource_id == str(sub_id)
    md = row.audit_metadata
    assert md["reason"] == "broker_flat"
    assert md["previous_mode"] == AUTO_MODE
    assert md["new_mode"] == MANUAL_MODE
    assert md["stored_quantity"] == 2
    assert md["broker_quantity"] == 0
    assert md["auto_revert"] is False       # one-way by design
    assert "detected_at" in md              # the timestamp
    assert row.created_at is not None


# ═══════════════════════════════════════════════════════════════════════
# NO DRIFT → NO FLIP
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_matching_position_does_not_flip(db_maker):
    sub_id = await _seed_sub(db_maker)
    async with db_maker() as db:
        sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=2,
            fetch_broker_position=_fetcher(2),
        )

    assert decision.flipped is False
    assert decision.reason == "no_drift"
    assert (await _load(db_maker, sub_id)).execution_mode == AUTO_MODE
    assert await _audit_count(db_maker, sub_id) == 0


@pytest.mark.asyncio
async def test_broker_holding_more_is_not_drift(db_maker):
    """A bigger broker position is the customer's own trade — not our bug."""
    sub_id = await _seed_sub(db_maker)
    async with db_maker() as db:
        sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=2,
            fetch_broker_position=_fetcher(5),
        )

    assert decision.flipped is False
    assert decision.reason == "no_drift"
    assert (await _load(db_maker, sub_id)).execution_mode == AUTO_MODE


# ═══════════════════════════════════════════════════════════════════════
# IDEMPOTENT — already MANUAL
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["offline", "one_click", "paper"])
async def test_already_manual_is_idempotent_noop(db_maker, mode):
    sub_id = await _seed_sub(db_maker, execution_mode=mode)
    async with db_maker() as db:
        sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=2,
            fetch_broker_position=_fetcher(0),   # would be drift if AUTO
        )

    assert decision.flipped is False
    assert decision.reason == "already_manual"
    # mode preserved exactly — not coerced to 'offline'
    assert (await _load(db_maker, sub_id)).execution_mode == mode
    assert await _audit_count(db_maker, sub_id) == 0


@pytest.mark.asyncio
async def test_double_check_writes_only_one_audit_row(db_maker):
    """Second pass sees MANUAL and no-ops — no duplicate flip/audit."""
    sub_id = await _seed_sub(db_maker)
    for _ in range(2):
        async with db_maker() as db:
            sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
            await check_and_flip_subscription(
                db, sub, symbol="BSE-FUT", stored_quantity=2,
                fetch_broker_position=_fetcher(0),
            )
    assert await _audit_count(db_maker, sub_id) == 1


# ═══════════════════════════════════════════════════════════════════════
# FAIL-SAFE — broker unreachable must NEVER flip
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ConnectionError("broker down"),
        TimeoutError("no response"),
        ValueError("garbage payload"),
        RuntimeError("session expired"),
    ],
)
async def test_broker_failure_does_not_flip(db_maker, exc):
    """An unreachable broker is not evidence of drift. Fail SAFE."""
    sub_id = await _seed_sub(db_maker)
    async with db_maker() as db:
        sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=2,
            fetch_broker_position=_raising_fetcher(exc),
        )

    assert decision.flipped is False
    assert decision.reason == "broker_unavailable"
    assert decision.drifted is False
    assert (await _load(db_maker, sub_id)).execution_mode == AUTO_MODE
    assert await _audit_count(db_maker, sub_id) == 0


@pytest.mark.asyncio
async def test_broker_none_means_flat_not_unknown(db_maker):
    """None = broker says flat (evidence) → drift. Distinct from a raise."""
    sub_id = await _seed_sub(db_maker)
    async with db_maker() as db:
        sub = (await db.execute(select(MarketplaceSubscription))).scalar_one()
        decision = await check_and_flip_subscription(
            db, sub, symbol="BSE-FUT", stored_quantity=2,
            fetch_broker_position=_fetcher(None),
        )
    assert decision.flipped is True
    assert decision.reason == "broker_flat"
    assert (await _load(db_maker, sub_id)).execution_mode == MANUAL_MODE


# ═══════════════════════════════════════════════════════════════════════
# SCOPE — a pure primitive: no orders, no scheduling
# ═══════════════════════════════════════════════════════════════════════


def test_module_places_no_orders_and_schedules_nothing():
    import inspect

    from app.services import subscriber_drift_service as mod

    src = inspect.getsource(mod)
    for forbidden in (
        "place_order", "DhanBroker", "FyersBroker", "square_off",
        "celery", "beat_schedule", "asyncio.create_task", "while True",
    ):
        assert forbidden not in src, f"drift service must not contain {forbidden!r}"


def test_does_not_import_marketplace_fanout():
    """A third importer would break the fan-out's 2-importer invariant."""
    import inspect

    from app.services import subscriber_drift_service as mod

    src = inspect.getsource(mod)
    assert "from app.services.marketplace_fanout" not in src
    assert "import marketplace_fanout" not in src
