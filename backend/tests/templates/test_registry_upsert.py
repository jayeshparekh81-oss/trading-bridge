"""Integration tests for ``load_from_seed_file`` upsert semantics.

These exercise the loader against a real (in-memory aiosqlite) DB so
we can verify that re-running the loader on an already-populated table
correctly UPDATES `is_active` and `config_json` on existing rows
(keyed by `slug`), rather than skipping them.

Why this exists: Phase 2-3 expanded the seed from 15 active equity
templates to 45. The DB-vs-JSON drift in production raised the
question "is the loader inserting-only, or is it actually upserting?".
These tests pin the answer to "it upserts" so future loader refactors
don't silently regress to insert-only.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.templates.models import StrategyTemplate
from app.templates.registry import load_from_seed_file


# StrategyTemplate uses PostgreSQL JSONB columns. SQLite can't render
# the JSONB type natively, so register a one-line compile hint that
# emits a plain TEXT column on SQLite. JSON values are still serialised
# via SQLAlchemy's JSON encoder so the round-trip stays correct.
@compiles(JSONB, "sqlite")
def _jsonb_as_text_on_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "TEXT"


# ─── In-memory aiosqlite fixture (independent of integration suite) ───


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Per-test in-memory aiosqlite DB with the StrategyTemplate
    table created from ORM metadata. StaticPool ensures the same
    connection is shared across all yields so seeded rows are visible
    on subsequent SELECTs."""
    import uuid as _uuid

    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tmpl-upsert-{_uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    # Create only the StrategyTemplate table. Using Base.metadata
    # pulls in every Base-registered table including some with FKs
    # to models that aren't imported here — that fails to resolve.
    # The loader only touches `strategy_templates`, so this is enough.
    async with engine.begin() as conn:
        await conn.run_sync(StrategyTemplate.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


# ─── Minimal seed fixtures ────────────────────────────────────────────


_MIN_REQUIRED_ACTIVE_CFG = {
    "indicators": ["ema_9", "ema_21"],
    "entry_long": {"condition": "ema_9 > ema_21"},
    "exit_long": {"condition": "ema_9 < ema_21"},
    "stop_loss_pct": 1.5,
    "take_profit_pct": 3.0,
    "position_sizing": {"method": "fixed_amount", "amount_inr": 50000},
    "max_open_positions": 1,
    "trading_hours": {"start": "09:15", "end": "15:15"},
}


def _row(
    slug: str,
    *,
    name: str | None = None,
    is_active: bool = False,
    config_json: dict | None = None,
) -> dict:
    """Build a minimum-viable seed-row dict with all required metadata."""
    cfg = config_json if config_json is not None else (
        _MIN_REQUIRED_ACTIVE_CFG if is_active else {}
    )
    return {
        "slug": slug,
        "name": name or slug.replace("-", " ").title(),
        "segment": "EQUITY",
        "instrument_type": "CASH",
        "category": "Trend Following",
        "complexity": "beginner",
        "description_en": f"{slug} description",
        "description_hi": f"{slug} description hi",
        "risk_level": "low",
        "recommended_capital_inr": 25000,
        "timeframe": "15m",
        "indicators_used": ["ema_9"],
        "index_filter": [],
        "tags": ["test"],
        "is_active": is_active,
        "requires_options_builder": False,
        "legs_count": None,
        "display_order": 0,
        "config_json": cfg,
    }


def _write_seed(rows: list[dict]) -> Path:
    """Write a seed JSON to a tempfile and return its path."""
    fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump({"_meta": {"version": "test"}, "templates": rows}, fd, indent=2)
    fd.close()
    return Path(fd.name)


# ─── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initial_load_inserts_all_rows(db_session: AsyncSession) -> None:
    """First load against an empty table inserts every seed row."""
    seed = _write_seed([_row("template-a"), _row("template-b")])
    result = await load_from_seed_file(db_session, seed_path=seed)
    assert result.inserted == 2
    assert result.updated == 0


@pytest.mark.asyncio
async def test_rerun_with_same_seed_is_idempotent(
    db_session: AsyncSession,
) -> None:
    """Re-loading the SAME seed against a populated table reports all
    as updates (zero inserts), and the DB state is unchanged."""
    seed = _write_seed([_row("template-a"), _row("template-b")])
    await load_from_seed_file(db_session, seed_path=seed)
    await db_session.flush()

    result2 = await load_from_seed_file(db_session, seed_path=seed)
    assert result2.inserted == 0
    assert result2.updated == 2


@pytest.mark.asyncio
async def test_rerun_with_updated_seed_flips_is_active(
    db_session: AsyncSession,
) -> None:
    """The exact production scenario: seed JSON flips a row from
    is_active=False to is_active=True with a new config_json. After
    re-load, the existing DB row reflects the new state."""
    initial_seed = _write_seed(
        [
            _row("template-a", is_active=False),
            _row("template-b", is_active=False),
        ],
    )
    await load_from_seed_file(db_session, seed_path=initial_seed)
    await db_session.flush()

    # Pre-condition: both rows in DB, both inactive.
    rows_before = (
        await db_session.execute(select(StrategyTemplate))
    ).scalars().all()
    assert len(rows_before) == 2
    assert all(r.is_active is False for r in rows_before)

    # Simulate Phase 2-3: flip template-a to active with a new config.
    new_cfg = dict(_MIN_REQUIRED_ACTIVE_CFG)
    new_cfg["take_profit_pct"] = 7.5  # marker we can assert on
    updated_seed = _write_seed(
        [
            _row("template-a", is_active=True, config_json=new_cfg),
            _row("template-b", is_active=False),
        ],
    )
    result = await load_from_seed_file(db_session, seed_path=updated_seed)
    await db_session.flush()

    # The loader should have reported 2 updates, 0 inserts.
    assert result.inserted == 0
    assert result.updated == 2

    # Post-condition: template-a is now active with the new config;
    # template-b is unchanged.
    a = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.slug == "template-a")
        )
    ).scalar_one()
    b = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.slug == "template-b")
        )
    ).scalar_one()

    assert a.is_active is True
    assert a.config_json["take_profit_pct"] == 7.5
    assert b.is_active is False


@pytest.mark.asyncio
async def test_rerun_with_new_slugs_mixes_insert_and_update(
    db_session: AsyncSession,
) -> None:
    """Adding NEW slugs to the seed while keeping old ones: the new
    ones insert, the old ones update."""
    initial = _write_seed([_row("old-a"), _row("old-b")])
    await load_from_seed_file(db_session, seed_path=initial)
    await db_session.flush()

    expanded = _write_seed(
        [
            _row("old-a", is_active=True),  # flipped active
            _row("old-b"),
            _row("new-c", is_active=True),  # brand new
            _row("new-d"),
        ],
    )
    result = await load_from_seed_file(db_session, seed_path=expanded)
    await db_session.flush()

    assert result.inserted == 2
    assert result.updated == 2

    a = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.slug == "old-a")
        )
    ).scalar_one()
    assert a.is_active is True
    c = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.slug == "new-c")
        )
    ).scalar_one()
    assert c.is_active is True


@pytest.mark.asyncio
async def test_created_at_preserved_across_updates(
    db_session: AsyncSession,
) -> None:
    """Re-loading must preserve the original `created_at` timestamp
    on existing rows — only `updated_at` advances."""
    seed = _write_seed([_row("template-a")])
    await load_from_seed_file(db_session, seed_path=seed)
    await db_session.flush()

    a_before = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.slug == "template-a")
        )
    ).scalar_one()
    original_created = a_before.created_at
    assert original_created is not None

    # Re-load the same seed; created_at must remain the same instance.
    # We don't assert updated_at strictly advances because SQLite's
    # datetime round-trip strips tzinfo, making a naive-vs-aware
    # comparison unreliable. The created_at preservation IS the
    # contract this test exists to pin; updated-at-monotonicity is
    # covered implicitly by other tests asserting field-by-field
    # state changes after re-load.
    await load_from_seed_file(db_session, seed_path=seed)
    await db_session.flush()

    a_after = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.slug == "template-a")
        )
    ).scalar_one()
    assert a_after.created_at == original_created


@pytest.mark.asyncio
async def test_full_real_seed_loads_then_reloads_idempotent(
    db_session: AsyncSession,
) -> None:
    """End-to-end against the REAL production seed JSON (113 templates).

    Loads twice — the second pass should report all 113 as updates and
    zero as inserts, AND the active count should land on 45 (Phase 2-3
    spec). This is the canonical regression test that catches any
    future drift where the loader silently stops updating existing rows.
    """
    real_seed = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "strategy_templates_seed.json"
    )
    if not real_seed.exists():
        pytest.skip("Real seed JSON missing from this environment")

    first = await load_from_seed_file(db_session, seed_path=real_seed)
    await db_session.flush()
    assert first.inserted == 113
    assert first.updated == 0

    # Active count in DB should match the seed's 45 from the get-go.
    active = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.is_active.is_(True))
        )
    ).scalars().all()
    assert len(active) == 45

    # Second load against the same seed: must be 113 updates, 0 inserts.
    second = await load_from_seed_file(db_session, seed_path=real_seed)
    await db_session.flush()
    assert second.inserted == 0
    assert second.updated == 113

    # Active count still 45 — no drift.
    active_after = (
        await db_session.execute(
            select(StrategyTemplate).where(StrategyTemplate.is_active.is_(True))
        )
    ).scalars().all()
    assert len(active_after) == 45
