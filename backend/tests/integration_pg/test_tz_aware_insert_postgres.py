"""The real INSERT, against real Postgres — the test that would have caught the
2026-09-03 subscribe outage on day one.

THE GAP THIS CLOSES. Every subscribe test ran on SQLite, which stores whatever
it is handed. Postgres via asyncpg does not: an aware ``datetime`` bound into
a parameter the ORM has typed as naive ``TIMESTAMP WITHOUT TIME ZONE`` raises

    asyncpg.exceptions.DataError: invalid input for query argument $3 …
    (can't subtract offset-naive and offset-aware datetimes)

and that is exactly how the first real customer's click 500'd. Seven models
carried the defect for four months while CI stayed green.

WHAT THIS DOES. Against a throwaway Postgres (docker-compose-test.yml,
localhost:5433) it applies the REAL alembic chain — not ``create_all`` — so the
DB columns are what the migrations made them (``timestamptz``), then drives
the exact ORM writes the incident's code paths perform, with ``datetime.now(UTC)``:

  * the free-subscribe INSERT (marketplace.py ``subscribe_to_listing``),
  * the publish UPDATE (``listing.published_at``),
  * the ledger snapshot + attestation INSERTs (``create_daily_snapshot``).

Every write is rolled back. A model whose annotation drifts back to naive
fails here with the incident's own error text, not on a customer.

RUNNING IT. ``docker compose -f docker-compose-test.yml up -d postgres_test``,
then pytest. If the DB is unreachable the module SKIPS with a loud reason —
unless ``REQUIRE_POSTGRES=1`` is set (CI), in which case it FAILS: a Postgres
test that quietly skips is the same hole this file exists to close.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/trading_bridge_test",
)
REQUIRE = os.environ.get("REQUIRE_POSTGRES") == "1"

pytestmark = pytest.mark.postgres


def _reachable() -> bool:
    async def probe() -> bool:
        engine = create_async_engine(TEST_DB_URL)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(probe())


if not _reachable():
    msg = (
        f"Postgres test DB unreachable at {TEST_DB_URL}. "
        "Start it: docker compose -f docker-compose-test.yml up -d postgres_test"
    )
    if REQUIRE:
        pytest.fail(msg + " (REQUIRE_POSTGRES=1 — a skipped Postgres test is the bug)")
    pytest.skip(msg, allow_module_level=True)


def _migrate_to_head() -> None:
    """Apply the REAL migration chain to the test DB (idempotent).

    In a SUBPROCESS, deliberately. ``migrations/env.py`` calls
    ``logging.config.fileConfig(...)``, which reconfigures logging for the
    whole process and disables existing loggers — running alembic in-process
    silently broke five log-capture tests in ``tests/observability/`` that
    happened to run afterwards. A subprocess also keeps the lru_cached
    ``get_settings()`` of the test process untouched.
    """
    import subprocess
    import sys

    backend_dir = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert proc.returncode == 0, f"alembic upgrade head failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.fixture(scope="module", autouse=True)
def _schema() -> None:
    _migrate_to_head()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DB_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


# ── the incident's exact columns are timestamptz in the MIGRATED schema ──


@pytest.mark.asyncio
async def test_migrated_columns_are_timestamptz(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            text(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE (table_name, column_name) IN ("
                "('marketplace_subscriptions','subscribed_at'),('marketplace_subscriptions','access_until'),"
                "('marketplace_listings','published_at'),('ledger_snapshots','created_at'),"
                "('ledger_attestations','attested_at'),('indicator_approval_queue','decision_at'),"
                "('indicator_status_overrides','approved_at'),('indicator_status_overrides','effective_from'),"
                "('indicator_status_overrides','effective_until'),('support_tickets','resolved_at'))"
            )
        )
    ).all()
    assert len(rows) == 10, rows
    assert {r[2] for r in rows} == {"timestamp with time zone"}, rows


# ── the free-subscribe INSERT, exactly as subscribe_to_listing builds it ──


async def _seed_listing(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """A creator, a strategy and a listing, via the ORM, with aware datetimes."""
    from app.db.models.marketplace_listing import MarketplaceListing
    from app.db.models.strategy import Strategy
    from app.db.models.user import User

    creator = User(email=f"{uuid.uuid4()}@pg.test", password_hash="x", is_active=True)
    session.add(creator)
    await session.flush()
    strategy = Strategy(user_id=creator.id, name="pg-tz-test", is_paper=True, is_active=False)
    session.add(strategy)
    await session.flush()
    listing = MarketplaceListing(
        creator_id=creator.id,
        strategy_id=strategy.id,
        title="pg-tz-test",
        description="",
        price_inr=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),  # the publish path's write
    )
    session.add(listing)
    await session.flush()
    return creator.id, listing.id


@pytest.mark.asyncio
async def test_free_subscribe_insert_binds_aware_datetime(session: AsyncSession) -> None:
    """🔴 THE INCIDENT. Before the fix this raised asyncpg DataError at flush."""
    from app.db.models.marketplace_subscription import MarketplaceSubscription
    from app.db.models.user import User

    _creator_id, listing_id = await _seed_listing(session)
    subscriber = User(email=f"{uuid.uuid4()}@pg.test", password_hash="x", is_active=True)
    session.add(subscriber)
    await session.flush()

    when = datetime.now(UTC)
    sub = MarketplaceSubscription(
        listing_id=listing_id,
        subscriber_id=subscriber.id,
        subscribed_at=when,
        status="active",
        amount_paid_inr=Decimal("0.00"),
        execution_mode="offline",
        is_paper=True,
        direction_filter="all",
    )
    session.add(sub)
    await session.flush()  # <- this is line 1061's failure point

    back = (
        await session.execute(
            select(MarketplaceSubscription.subscribed_at).where(MarketplaceSubscription.id == sub.id)
        )
    ).scalar_one()
    assert back.tzinfo is not None, "round-trip lost the timezone"
    assert back == when


@pytest.mark.asyncio
async def test_publish_update_binds_aware_datetime(session: AsyncSession) -> None:
    from app.db.models.marketplace_listing import MarketplaceListing

    _creator_id, listing_id = await _seed_listing(session)
    listing = await session.get(MarketplaceListing, listing_id)
    assert listing is not None
    listing.published_at = datetime.now(UTC)  # marketplace.py:813
    await session.flush()


@pytest.mark.asyncio
async def test_ledger_snapshot_and_attestation_bind_aware_datetimes(session: AsyncSession) -> None:
    """The snapshot trigger writes created_at / attested_at with datetime.now(UTC)."""
    from app.db.models.ledger_attestation import LedgerAttestation
    from app.db.models.ledger_snapshot import LedgerSnapshot

    _creator_id, listing_id = await _seed_listing(session)
    snap = LedgerSnapshot(
        listing_id=listing_id,
        snapshot_date=datetime.now(UTC).date(),
        sequence_number=1,
        cumulative_pnl_inr=Decimal("0"),
        max_drawdown_pct=Decimal("0"),
        total_trades=0,
        win_rate=Decimal("0"),
        sharpe_ratio=None,
        days_since_publish=0,
        paper_trades_count=0,
        live_trades_count=0,
        data_hash="h" * 64,
        prior_hash=None,
        chain_signature="c" * 64,
        created_at=datetime.now(UTC),  # snapshots.py:279
    )
    session.add(snap)
    await session.flush()
    att = LedgerAttestation(
        snapshot_id=snap.id,
        attestation_type="daily_snapshot",
        attestation_hash="a" * 64,
        polygon_tx_hash=None,
        attested_at=datetime.now(UTC),  # snapshots.py:292
    )
    session.add(att)
    await session.flush()
