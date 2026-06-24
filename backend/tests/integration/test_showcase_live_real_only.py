"""Showcase ``/live`` counts only genuinely-RECONCILED REAL trades.

Credibility fix. The old count keyed off the strategy's CURRENT ``is_paper=false``
+ ``final_pnl IS NOT NULL``, so a STALE PAPER position (``broker_order_id
'PAPER-…'``, manually-closed ``final_pnl=0``) was reported as a "live reconciled"
trade, while real-but-unreconciled trades were hidden. The fixed query requires a
REAL broker fill (``broker_order_id NOT LIKE 'PAPER-%'`` on the position's signal)
AND a reconciled ``final_pnl``. These tests run the ACTUAL SQL against a real
(sqlite) session with seeded positions/executions.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles as _compiles
from sqlalchemy.pool import StaticPool

from app.api import showcase_api as api
from app.api.showcase_api import _count_reconciled_real_trades
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition


@_compiles(_JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:sc-{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


# A real Dhan-style id (numeric) vs a paper sim id.
REAL_OID = "222260520454106"
PAPER_OID = "PAPER-5c849d5d-861d-4f7a-a450-6b137f6b1ce9"


async def _strategy(s: AsyncSession, *, is_paper: bool, force_id: uuid.UUID | None = None) -> uuid.UUID:
    st = Strategy(user_id=uuid.uuid4(), name="BSE LTD Futures", is_paper=is_paper)
    if force_id is not None:
        st.id = force_id
    s.add(st)
    await s.flush()
    return st.id


async def _position(
    s: AsyncSession, *, strategy_id: uuid.UUID, signal_id: uuid.UUID, final_pnl: Decimal | None
) -> None:
    s.add(StrategyPosition(
        user_id=uuid.uuid4(), strategy_id=strategy_id, broker_credential_id=uuid.uuid4(),
        signal_id=signal_id, symbol="BSE", side="buy", total_quantity=375,
        remaining_quantity=0, status="closed", final_pnl=final_pnl,
    ))


async def _execution(s: AsyncSession, *, signal_id: uuid.UUID, broker_order_id: str) -> None:
    s.add(StrategyExecution(
        signal_id=signal_id, broker_credential_id=uuid.uuid4(), leg_number=1,
        leg_role="entry", symbol="BSE", side="buy", quantity=375,
        order_type="market", broker_order_id=broker_order_id,
    ))


def _pfx(sid: uuid.UUID) -> str:
    return str(sid)[:8]


# ── (a) a PAPER position is NEVER counted (even with final_pnl + live strategy) ──


@pytest.mark.asyncio
async def test_paper_position_never_counted(session: AsyncSession) -> None:
    sid = await _strategy(session, is_paper=False)  # LIVE strategy
    sig = uuid.uuid4()
    await _position(session, strategy_id=sid, signal_id=sig, final_pnl=Decimal("0"))  # final_pnl SET
    await _execution(session, signal_id=sig, broker_order_id=PAPER_OID)  # but the fill is PAPER
    await session.commit()
    assert await _count_reconciled_real_trades(session, _pfx(sid)) == 0


# ── (b) a REAL but UNRECONCILED position is not counted (final_pnl NULL) ──


@pytest.mark.asyncio
async def test_real_unreconciled_not_counted(session: AsyncSession) -> None:
    sid = await _strategy(session, is_paper=False)
    sig = uuid.uuid4()
    await _position(session, strategy_id=sid, signal_id=sig, final_pnl=None)  # not reconciled
    await _execution(session, signal_id=sig, broker_order_id=REAL_OID)  # real fill
    await session.commit()
    assert await _count_reconciled_real_trades(session, _pfx(sid)) == 0


# ── a REAL + RECONCILED position IS counted ──


@pytest.mark.asyncio
async def test_real_reconciled_is_counted(session: AsyncSession) -> None:
    sid = await _strategy(session, is_paper=False)
    sig = uuid.uuid4()
    await _position(session, strategy_id=sid, signal_id=sig, final_pnl=Decimal("1234.56"))
    await _execution(session, signal_id=sig, broker_order_id="999260520454106")  # real
    await session.commit()
    assert await _count_reconciled_real_trades(session, _pfx(sid)) == 1


# ── a PAPER strategy (is_paper=true) is excluded entirely ──


@pytest.mark.asyncio
async def test_paper_strategy_excluded(session: AsyncSession) -> None:
    sid = await _strategy(session, is_paper=True)  # paper strategy
    sig = uuid.uuid4()
    await _position(session, strategy_id=sid, signal_id=sig, final_pnl=Decimal("100"))
    await _execution(session, signal_id=sig, broker_order_id=REAL_OID)
    await session.commit()
    assert await _count_reconciled_real_trades(session, _pfx(sid)) == 0


# ── (c) the BSE scenario end-to-end: stale paper + real-unreconciled → honest 0 ──


@pytest.mark.asyncio
async def test_bse_scenario_renders_honest_zero(session: AsyncSession) -> None:
    """Reproduces prod BSE: one stale PAPER position with final_pnl + several REAL
    but unreconciled trades. ``showcase_live`` must render the honest 0-state
    ('tracking active, none reconciled') and NEVER any P&L."""
    bse_id = uuid.UUID("89423ecc-0000-0000-0000-000000000001")  # matches _LIVE_STRATEGY['bse']
    await _strategy(session, is_paper=False, force_id=bse_id)
    # the stale paper position (the bug row) — final_pnl set, PAPER fill
    sig_p = uuid.uuid4()
    await _position(session, strategy_id=bse_id, signal_id=sig_p, final_pnl=Decimal("0"))
    await _execution(session, signal_id=sig_p, broker_order_id=PAPER_OID)
    # real trades, NOT yet reconciled
    for oid in ("222260520454106", "23226060447806", "34226061278006"):
        sg = uuid.uuid4()
        await _position(session, strategy_id=bse_id, signal_id=sg, final_pnl=None)
        await _execution(session, signal_id=sg, broker_order_id=oid)
    await session.commit()

    # direct count
    assert await _count_reconciled_real_trades(session, "89423ecc") == 0

    # end-to-end endpoint: honest 0-state, no fabricated P&L
    res = await api.showcase_live("bse", session=session)
    assert res["status"] == "tracking_active"
    assert res["reconciled_trades"] == 0
    assert "no trades reconciled" in res["note"].lower()
    blob = json.dumps(res).lower()
    assert "pnl" not in blob and "₹" not in blob and "profit" not in blob
