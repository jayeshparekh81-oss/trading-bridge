"""Regression test — GET /api/strategies/{id} surfaces template_origin.

Backs the Task-4-Resolution UX fix: cloned-from-template strategies must
include a ``template_origin`` block in the response so the frontend can
distinguish them from genuine pre-Phase-5 legacy rows. Hand-built
strategies (no row in ``strategy_template_origin``) must continue to
return ``template_origin = null``.

The detail page reads this field to:
  - suppress the "Phase 5 builder se pehle bani thi" legacy warning,
  - render the "Cloned from template" badge + template defaults preview,
  - swap "Backtest unavailable (no DSL)" for "Available with Strategy Builder".

Two cases:
  1. Strategy with a matching origin row + template → response carries
     a populated template_origin object with slug, name, category,
     complexity, cloned_at, config_json.
  2. Strategy without an origin row → response.template_origin is None.

Uses the same in-memory aiosqlite fixture stack as the rest of
``backend/tests/strategy_engine/api/``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.templates.models import StrategyTemplate, StrategyTemplateOrigin


# ─── sqlite dialect shim for JSONB ──────────────────────────────────────
# ``app.templates.models.StrategyTemplate`` uses Postgres JSONB for
# ``config_json``, ``indicators_used``, ``index_filter``, ``tags``.
# In production those columns travel over asyncpg and JSONB is exactly
# right; in this in-memory aiosqlite test harness JSONB cannot be
# compiled. Registering a dialect-specific compiler routes JSONB →
# vanilla JSON on the sqlite path only. No effect on the Postgres path
# (production + integration tests) because @compiles is per-dialect.

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


# ─── helpers ───────────────────────────────────────────────────────────


_TEMPLATE_CONFIG_JSON = {
    "indicators": ["parabolic_sar"],
    "entry_long": {"condition": "parabolic_sar flips below close"},
    "exit_long": {"condition": "parabolic_sar flips above close"},
    "stop_loss_pct": 1.5,
    "take_profit_pct": 3.5,
    "position_sizing": {"method": "fixed_amount", "amount_inr": 30000},
    "max_open_positions": 1,
    "trading_hours": {"start": "09:15", "end": "15:15"},
}


async def _seed_cloned_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    user: User,
) -> tuple[Strategy, StrategyTemplate]:
    """Seed one Strategy + one StrategyTemplate + one StrategyTemplateOrigin
    row, mirroring exactly what ``clone_service.clone_template`` writes.

    Returns the strategy + template for assertion convenience.
    """
    async with maker() as session:
        now = datetime.now(UTC)
        template = StrategyTemplate(
            id=uuid.uuid4(),
            slug="parabolic-sar-reversal",
            name="Parabolic SAR Reversal",
            segment="equity",
            instrument_type="stock",
            category="Trend Following",
            complexity="beginner",
            description_en="PSAR flip-driven entries",
            description_hi="",
            config_json=_TEMPLATE_CONFIG_JSON,
            risk_level="medium",
            recommended_capital_inr=30000,
            timeframe="5m",
            indicators_used=["parabolic_sar"],
            index_filter=[],
            tags=["psar", "trend"],
            is_active=True,
            requires_options_builder=False,
            legs_count=None,
            display_order=0,
            created_at=now,
            updated_at=now,
        )
        session.add(template)
        await session.flush()

        strategy = Strategy(
            user_id=user.id,
            name="Parabolic SAR Reversal (from template)",
            webhook_token_id=None,
            broker_credential_id=None,
            max_position_size=0,
            allowed_symbols=[],
            is_active=True,
            strategy_json=None,
        )
        session.add(strategy)
        await session.flush()

        origin = StrategyTemplateOrigin(
            strategy_id=strategy.id,
            template_id=template.id,
            template_slug=template.slug,
            cloned_at=now,
        )
        session.add(origin)
        await session.commit()
        await session.refresh(strategy)
        await session.refresh(template)
        return strategy, template


async def _seed_handbuilt_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    user: User,
) -> Strategy:
    """Seed a Strategy with NO template_origin row — the hand-built
    case the response must report as template_origin = null."""
    async with maker() as session:
        strategy = Strategy(
            user_id=user.id,
            name="Hand-built EMA cross",
            webhook_token_id=None,
            broker_credential_id=None,
            max_position_size=0,
            allowed_symbols=[],
            is_active=True,
            strategy_json={"indicators": [{"id": "ema_9"}]},
        )
        session.add(strategy)
        await session.commit()
        await session.refresh(strategy)
        return strategy


# ─── tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_strategy_includes_template_origin_when_cloned(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """A cloned strategy must surface the template_origin block."""
    strategy, template = await _seed_cloned_strategy(
        db_session_maker, user=seed_user
    )

    resp = client.get(f"/api/strategies/{strategy.id}")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["id"] == str(strategy.id)
    assert body["strategy_json"] is None  # cloned rows carry no DSL

    origin = body["template_origin"]
    assert origin is not None, (
        "template_origin must be populated for a cloned strategy"
    )
    assert origin["template_slug"] == template.slug
    assert origin["template_name"] == template.name
    assert origin["template_category"] == template.category
    assert origin["template_complexity"] == template.complexity
    assert origin["cloned_at"] is not None
    assert origin["config_json"]["stop_loss_pct"] == 1.5
    assert origin["config_json"]["take_profit_pct"] == 3.5
    assert origin["config_json"]["indicators"] == ["parabolic_sar"]


@pytest.mark.asyncio
async def test_get_strategy_template_origin_is_null_for_handbuilt(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """A hand-built strategy (no origin row) must return template_origin=null."""
    strategy = await _seed_handbuilt_strategy(db_session_maker, user=seed_user)

    resp = client.get(f"/api/strategies/{strategy.id}")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["id"] == str(strategy.id)
    assert body["strategy_json"] is not None
    assert body["template_origin"] is None
