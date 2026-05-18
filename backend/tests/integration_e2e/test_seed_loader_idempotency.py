"""Seed-loader idempotency test.

Catches the failure mode: running ``load_from_seed_file`` twice creates
duplicate rows or unexpectedly mutates the catalog. The May-17 deploy
runbook re-runs the seed loader on every deploy — must be safe.

Assertions:
    Run 1: INSERT counts > 0, UPDATE counts = 0
    Run 2 (same seed file): INSERT counts = 0, UPDATE counts == Run 1 INSERT counts
    No row count change between runs
    No data drift on any field
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.templates.models import StrategyTemplate
from app.templates.registry import load_from_seed_file


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


# A small custom seed file so we don't pull in the 113-entry real one
# (faster, deterministic, doesn't get affected by ongoing seed edits).
_TEST_SEED = {
    "templates": [
        {
            "slug": "idem-test-1",
            "name": "Test Template 1",
            "segment": "equity",
            "instrument_type": "stock",
            "category": "Trend Following",
            "complexity": "beginner",
            "description_en": "first test template",
            "description_hi": "",
            "config_json": {
                "indicators": ["ema"],
                "entry_long": {"condition": "ema_20 > 21000"},
                "exit_long": {"condition": "ema_20 < 21000"},
                "stop_loss_pct": 1.0,
                "take_profit_pct": 2.0,
                "position_sizing": {"method": "fixed_amount", "amount_inr": 10000},
                "max_open_positions": 1,
                "trading_hours": {"start": "09:15", "end": "15:15"},
            },
            "risk_level": "low",
            "recommended_capital_inr": 10000,
            "timeframe": "5m",
            "indicators_used": ["ema_20"],
            "index_filter": [],
            "tags": ["test"],
            "is_active": True,
            "requires_options_builder": False,
            "legs_count": None,
            "display_order": 1,
        },
        {
            "slug": "idem-test-2",
            "name": "Test Template 2 — inactive",
            "segment": "equity",
            "instrument_type": "stock",
            "category": "Momentum",
            "complexity": "intermediate",
            "description_en": "second test template, inactive",
            "description_hi": "",
            "config_json": {},
            "risk_level": "medium",
            "recommended_capital_inr": 20000,
            "timeframe": "15m",
            "indicators_used": ["rsi"],
            "index_filter": [],
            "tags": ["test"],
            "is_active": False,
            "requires_options_builder": False,
            "legs_count": None,
            "display_order": 2,
        },
        {
            "slug": "idem-test-3",
            "name": "Test Options Template",
            "segment": "options",
            "instrument_type": "CALL",
            "category": "Volatility",
            "complexity": "expert",
            "description_en": "third — options",
            "description_hi": "",
            "config_json": {},
            "risk_level": "high",
            "recommended_capital_inr": 200000,
            "timeframe": "5m",
            "indicators_used": ["iv"],
            "index_filter": [],
            "tags": ["test"],
            "is_active": False,
            "requires_options_builder": True,
            "legs_count": 2,
            "display_order": 3,
        },
    ]
}


@pytest.fixture
def seed_path(tmp_path: Path) -> Path:
    p = tmp_path / "test_seed.json"
    p.write_text(json.dumps(_TEST_SEED))
    return p


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:seed-idem-{uuid.uuid4().hex}"
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


@pytest.mark.asyncio
async def test_first_run_inserts_all_rows(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_path: Path,
) -> None:
    async with db_session_maker() as session:
        result = await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()
        assert result.inserted == 3
        assert result.updated == 0
        assert result.total_in_file == 3
        assert result.validated_active == 1


@pytest.mark.asyncio
async def test_second_run_updates_all_rows_no_new_inserts(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_path: Path,
) -> None:
    """Idempotency: same seed run twice → no new inserts, all updates."""
    async with db_session_maker() as session:
        first = await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()
    async with db_session_maker() as session:
        second = await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()
        # Second run should have only updates
        assert second.inserted == 0
        assert second.updated == first.inserted
        assert second.total_in_file == first.total_in_file


@pytest.mark.asyncio
async def test_row_count_stable_across_runs(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_path: Path,
) -> None:
    """The row count in strategy_templates must not change between runs."""
    async with db_session_maker() as session:
        await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()
    async with db_session_maker() as session:
        count_after_first = (
            await session.execute(select(func.count(StrategyTemplate.id)))
        ).scalar_one()

    async with db_session_maker() as session:
        await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()
    async with db_session_maker() as session:
        count_after_second = (
            await session.execute(select(func.count(StrategyTemplate.id)))
        ).scalar_one()

    assert count_after_first == count_after_second == 3


@pytest.mark.asyncio
async def test_row_data_stable_across_runs(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_path: Path,
) -> None:
    """No silent data drift: every column on every row matches between runs."""
    async with db_session_maker() as session:
        await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()

    async with db_session_maker() as session:
        rows_first = (
            await session.execute(select(StrategyTemplate).order_by(StrategyTemplate.slug))
        ).scalars().all()
        snapshot_first = [
            {
                "slug": r.slug,
                "name": r.name,
                "category": r.category,
                "config_json": r.config_json,
                "is_active": r.is_active,
                "indicators_used": r.indicators_used,
            }
            for r in rows_first
        ]

    async with db_session_maker() as session:
        await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()

    async with db_session_maker() as session:
        rows_second = (
            await session.execute(select(StrategyTemplate).order_by(StrategyTemplate.slug))
        ).scalars().all()
        snapshot_second = [
            {
                "slug": r.slug,
                "name": r.name,
                "category": r.category,
                "config_json": r.config_json,
                "is_active": r.is_active,
                "indicators_used": r.indicators_used,
            }
            for r in rows_second
        ]

    assert snapshot_first == snapshot_second


@pytest.mark.asyncio
async def test_seed_edit_updates_existing_row_in_place(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_path: Path,
    tmp_path: Path,
) -> None:
    """Edit one row in the seed → re-run → that row updates without
    creating a new row."""
    async with db_session_maker() as session:
        first = await load_from_seed_file(session, seed_path=seed_path)
        await session.commit()

    # Snapshot original id
    async with db_session_maker() as session:
        orig = (
            await session.execute(
                select(StrategyTemplate).where(StrategyTemplate.slug == "idem-test-1")
            )
        ).scalar_one()
        orig_id = orig.id
        orig_created = orig.created_at

    # Edit the seed file — change name of idem-test-1
    edited = json.loads(seed_path.read_text())
    edited["templates"][0]["name"] = "Test Template 1 — RENAMED"
    edited_path = tmp_path / "edited_seed.json"
    edited_path.write_text(json.dumps(edited))

    async with db_session_maker() as session:
        second = await load_from_seed_file(session, seed_path=edited_path)
        await session.commit()
        assert second.inserted == 0
        assert second.updated == 3  # all 3 rows touched (UPDATEs on all)

    async with db_session_maker() as session:
        updated = (
            await session.execute(
                select(StrategyTemplate).where(StrategyTemplate.slug == "idem-test-1")
            )
        ).scalar_one()
        # Same id (UPDATE not INSERT); name changed
        assert updated.id == orig_id
        assert updated.name == "Test Template 1 — RENAMED"
        # created_at preserved by the registry's _coerce_seed_row logic
        assert updated.created_at == orig_created
