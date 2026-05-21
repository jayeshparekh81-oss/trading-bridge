"""Queue CC Phase 1c — clone_service translator hookup tests.

Three coverage targets:
    1. PASS path: cloning a template the translator can handle (e.g.
       ema-crossover-9-21 shape) sets ``strategy.strategy_json`` to a
       canonical dict.
    2. FAIL path: cloning a template the translator can't parse leaves
       ``strategy.strategy_json`` ``None``; the clone itself still
       succeeds (no exception).
    3. Defensive path: an UNEXPECTED exception inside the translator
       must not fail the clone — wrapped in a broad except.

Uses the same aiosqlite + JSONB shim pattern as
``tests/strategy_engine/api/test_get_strategy_with_template_origin.py``.
"""

from __future__ import annotations

import uuid as _uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.user import User
from app.templates.clone_service import clone_template
from app.templates.models import StrategyTemplate


# JSONB → JSON shim for sqlite test path (mirrors the pattern used in
# other template tests). Postgres production code path is unaffected
# because @compiles is per-dialect.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


# ─── fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-clone-translator-{_uuid.uuid4().hex}"
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


_PASS_CONFIG: dict[str, Any] = {
    # Mirror the Queue BB ema-crossover-9-21 shape — known to translate
    # cleanly per docs/TRANSLATOR_PROTOTYPE/PROGRESS.md.
    "indicators": ["ema_9", "ema_21"],
    "entry_long": {"condition": "ema_9 crosses above ema_21"},
    "exit_long": {"condition": "ema_9 crosses below ema_21"},
    "stop_loss_pct": 1.5,
    "take_profit_pct": 3.0,
    "position_sizing": {"method": "fixed_amount", "amount_inr": 50000},
    "max_open_positions": 1,
    "trading_hours": {"start": "09:15", "end": "15:15"},
}

_FAIL_CONFIG: dict[str, Any] = {
    # Prose the parser doesn't handle (multi-bar lookback + divergence) —
    # mirrors the ``rsi-divergence`` template family in PROGRESS.md.
    "indicators": ["rsi_14"],
    "entry_long": {
        "condition": "price prints lower low in last 20 bars AND rsi_14 prints higher low"
    },
    "exit_long": {"condition": "rsi_14 > 70"},
    "stop_loss_pct": 1.5,
    "take_profit_pct": 3.0,
    "position_sizing": {"method": "fixed_amount", "amount_inr": 50000},
    "max_open_positions": 1,
    "trading_hours": {"start": "09:15", "end": "15:15"},
}


async def _seed(
    maker: async_sessionmaker[AsyncSession],
    *,
    slug: str,
    config: dict[str, Any],
) -> tuple[User, StrategyTemplate]:
    """Insert one user + one StrategyTemplate. Returns ORM rows reloaded
    in a fresh session so the test can pass them to clone_template
    without lifetime issues."""
    now = datetime.now(UTC)
    async with maker() as session:
        user = User(email=f"{slug}@test.local", password_hash="x", is_active=True)
        template = StrategyTemplate(
            id=_uuid.uuid4(),
            slug=slug,
            name=slug.replace("-", " ").title(),
            segment="EQUITY",
            instrument_type="CASH",
            category="Trend Following",
            complexity="beginner",
            description_en="test template",
            description_hi="",
            config_json=config,
            risk_level="low",
            recommended_capital_inr=50000,
            timeframe="5m",
            indicators_used=config.get("indicators", []),
            index_filter=[],
            tags=["test"],
            is_active=True,
            requires_options_builder=False,
            legs_count=None,
            display_order=0,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, template])
        await session.commit()
        await session.refresh(user)
        await session.refresh(template)
        return user, template


# ─── tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clone_pass_template_sets_strategy_json(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """A template whose prose the translator handles must produce a
    Strategy row with ``strategy_json`` populated as a dict — exactly
    what the existing ``/api/strategies/{id}/backtest`` endpoint
    validates via ``StrategyJSON.model_validate``."""
    user, _template = await _seed(
        db_maker, slug="ema-crossover-9-21-test", config=_PASS_CONFIG
    )
    async with db_maker() as session:
        strategy, _src = await clone_template(
            session, user, "ema-crossover-9-21-test"
        )
        await session.commit()
        await session.refresh(strategy)

    assert isinstance(strategy.strategy_json, dict), (
        f"strategy_json should be a dict (translator PASS), got "
        f"{type(strategy.strategy_json).__name__}"
    )
    # Sanity-check field map: indicators carry through, id is namespaced.
    assert strategy.strategy_json["id"].startswith("template:")
    inds = strategy.strategy_json["indicators"]
    assert {ind["id"] for ind in inds} >= {"ema_9", "ema_21"}


@pytest.mark.asyncio
async def test_clone_fail_template_leaves_null_strategy_json(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """A template the translator can't parse must NOT raise — clone
    still succeeds, strategy_json stays NULL, and the existing frontend
    "Phase 5 builder not yet shipped" copy fires via the hasDsl gate.
    This is the defensive contract the whole Queue CC hybrid hinges on.
    """
    user, _template = await _seed(
        db_maker, slug="rsi-divergence-test", config=_FAIL_CONFIG
    )
    async with db_maker() as session:
        strategy, _src = await clone_template(
            session, user, "rsi-divergence-test"
        )
        await session.commit()
        await session.refresh(strategy)

    assert strategy.strategy_json is None, (
        f"strategy_json should be None on translator FAIL, got "
        f"{type(strategy.strategy_json).__name__}: {strategy.strategy_json}"
    )
    # The row itself must still be intact.
    assert strategy.user_id == user.id
    assert strategy.name.startswith("Rsi Divergence Test")


@pytest.mark.asyncio
async def test_clone_unexpected_translator_error_is_safe(
    db_maker: async_sessionmaker[AsyncSession],
) -> None:
    """If the translator raises an UNEXPECTED (non-TranslationError)
    exception — e.g. ``RuntimeError`` from a bug we haven't seen — the
    clone path's broad-except must still leave the user with a valid
    Strategy row. Logging captures the incident; clone never blocks on
    translator bugs.
    """
    user, _template = await _seed(
        db_maker, slug="unexpected-error-test", config=_PASS_CONFIG
    )
    # Monkey-patch the translator entry point to throw an unrelated
    # exception. The clone path catches Exception below TranslationError
    # so this should still succeed.
    with patch(
        "app.templates.clone_service.translate_template",
        side_effect=RuntimeError("simulated unexpected bug"),
    ):
        async with db_maker() as session:
            strategy, _src = await clone_template(
                session, user, "unexpected-error-test"
            )
            await session.commit()
            await session.refresh(strategy)

    assert strategy.strategy_json is None
    assert strategy.user_id == user.id
