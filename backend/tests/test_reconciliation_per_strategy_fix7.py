"""Fix #7 — Reconciliation per-strategy aware (no more global gate).

See /tmp/7_RECONCILIATION.md.

Pre-fix: ``reconcile_once`` no-opped when global ``STRATEGY_PAPER_MODE``
was True.  Mixed-mode deployment (global paper, BSE LTD live) silenced
drift detection — the May 20 phantom position lived 7.5 hours undetected.

Fix: replace global gate with per-strategy filter — only credentials
backing ≥1 live strategy (``Strategy.is_paper=False``) are reconciled.
Inside ``_reconcile_credential``, the DB-side query joins to
``strategies`` and filters to live-strategy positions only, so a
credential shared by paper + live strategies doesn't surface paper
positions as false ``db_only`` drift.

Tests below use an in-memory aiosqlite engine (same pattern as
``test_per_strategy_paper_flag.py``), independent of the broken
JSONB-on-SQLite fixture in ``tests/integration/conftest.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.brokers.base import BrokerInterface
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.user import User
from app.schemas.broker import BrokerName, Exchange, Position, ProductType
from app.workers.reconciliation_loop import (
    _list_credentials_backing_live_strategies,
    reconcile_once,
)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _seed_user_and_credential(db: AsyncSession) -> tuple[User, BrokerCredential]:
    """Common setup: one user + one Dhan credential (no strategy)."""
    user = User(email="recon-test@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()
    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SECRET"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred)
    await db.flush()
    return user, cred


def _make_strategy(
    user_id: Any, cred_id: Any, *, is_paper: bool, name: str = "s"
) -> Strategy:
    return Strategy(
        user_id=user_id,
        name=name,
        broker_credential_id=cred_id,
        entry_lots=1,
        partial_profit_lots=0,
        trail_lots=0,
        allowed_symbols=["NIFTY"],
        ai_validation_enabled=False,
        is_active=True,
        is_paper=is_paper,
    )


# ═══════════════════════════════════════════════════════════════════════
# Credential filter (Fix #7 primary change)
# ═══════════════════════════════════════════════════════════════════════


async def test_credential_filter_returns_only_live_backers(
    db: AsyncSession,
) -> None:
    """Credential backing a live strategy → included. Credential backing
    only paper strategies → excluded."""
    user, cred_live = await _seed_user_and_credential(db)

    # Second credential — backs only a paper strategy.
    cred_paper = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc=encrypt_credential("CID2"),
        api_key_enc=encrypt_credential("KEY2"),
        api_secret_enc=encrypt_credential("SECRET2"),
        access_token_enc=encrypt_credential("TOK2"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred_paper)
    await db.flush()

    db.add(_make_strategy(user.id, cred_live.id, is_paper=False, name="live"))
    db.add(_make_strategy(user.id, cred_paper.id, is_paper=True, name="paper"))
    await db.commit()

    rows = await _list_credentials_backing_live_strategies(db)
    cred_ids = {r.id for r in rows}
    assert cred_live.id in cred_ids
    assert cred_paper.id not in cred_ids


async def test_credential_filter_excludes_inactive_credentials(
    db: AsyncSession,
) -> None:
    """Live strategy pointing at inactive credential → still excluded
    (BrokerCredential.is_active=False)."""
    user, cred = await _seed_user_and_credential(db)
    cred.is_active = False
    db.add(_make_strategy(user.id, cred.id, is_paper=False))
    await db.commit()

    rows = await _list_credentials_backing_live_strategies(db)
    assert rows == []


async def test_credential_filter_excludes_inactive_strategies(
    db: AsyncSession,
) -> None:
    """Live strategy with is_active=False → excluded even if is_paper=False."""
    user, cred = await _seed_user_and_credential(db)
    strat = _make_strategy(user.id, cred.id, is_paper=False)
    strat.is_active = False
    db.add(strat)
    await db.commit()

    rows = await _list_credentials_backing_live_strategies(db)
    assert rows == []


# ═══════════════════════════════════════════════════════════════════════
# reconcile_once integration
# ═══════════════════════════════════════════════════════════════════════


def _stub_broker_class(monkeypatch: pytest.MonkeyPatch, positions: list[Position]) -> MagicMock:
    """Install a stub get_broker_class that returns a broker reporting
    the given live positions."""
    broker_mock = MagicMock(spec=BrokerInterface)
    broker_mock.is_session_valid = AsyncMock(return_value=True)
    broker_mock.login = AsyncMock(return_value=True)
    broker_mock.get_positions = AsyncMock(return_value=positions)

    class _StubBrokerCls:
        def __init__(self, _creds: Any) -> None:
            pass

        def __new__(cls, _creds: Any) -> Any:  # type: ignore[misc]
            return broker_mock

    monkeypatch.setattr(
        "app.brokers.registry.get_broker_class",
        lambda _name: _StubBrokerCls,
    )
    return broker_mock


async def test_reconcile_once_skips_when_only_paper_strategies(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-fix this would have been gated by global STRATEGY_PAPER_MODE;
    now it's gated by absence of live strategies — same outcome for the
    all-paper case, no broker call."""
    user, cred = await _seed_user_and_credential(db)
    db.add(_make_strategy(user.id, cred.id, is_paper=True))
    await db.commit()

    # Sentinel — broker class must NOT be looked up.
    monkeypatch.setattr(
        "app.brokers.registry.get_broker_class",
        lambda _n: pytest.fail("broker should not be built when no live strategies"),
    )

    mismatches = await reconcile_once(db)
    assert mismatches == 0


async def test_reconcile_once_runs_for_live_strategy_in_mixed_mode(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact May-20 scenario: global STRATEGY_PAPER_MODE could be
    anything; one strategy is is_paper=False. The reconciliation must
    now run for it. Broker reports same position → no drift."""
    user, cred = await _seed_user_and_credential(db)
    strat = _make_strategy(user.id, cred.id, is_paper=False)
    db.add(strat)
    await db.flush()
    db.add(
        StrategyPosition(
            user_id=user.id,
            strategy_id=strat.id,
            broker_credential_id=cred.id,
            symbol="NIFTY",
            side="buy",
            total_quantity=1,
            remaining_quantity=1,
            avg_entry_price=Decimal("22500.0"),
            status="open",
        )
    )
    await db.commit()

    _stub_broker_class(
        monkeypatch,
        positions=[
            Position(
                symbol="NIFTY",
                exchange=Exchange.NFO,
                quantity=1,
                avg_price=Decimal("22500.0"),
                ltp=Decimal("22510.0"),
                unrealized_pnl=Decimal("100.0"),
                product_type=ProductType.MARGIN,
            )
        ],
    )

    mismatches = await reconcile_once(db)
    assert mismatches == 0


async def test_reconcile_once_detects_phantom_db_only_position(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact May-20 incident: DB has an open position, broker has
    nothing. Reconciliation must report 1 mismatch (db_only side)."""
    user, cred = await _seed_user_and_credential(db)
    strat = _make_strategy(user.id, cred.id, is_paper=False)
    db.add(strat)
    await db.flush()
    db.add(
        StrategyPosition(
            user_id=user.id,
            strategy_id=strat.id,
            broker_credential_id=cred.id,
            symbol="BSE",
            side="buy",
            total_quantity=1500,
            remaining_quantity=1500,
            avg_entry_price=None,  # phantom — no fill price
            status="open",
        )
    )
    await db.commit()

    _stub_broker_class(monkeypatch, positions=[])  # broker has NOTHING

    mismatches = await reconcile_once(db)
    assert mismatches == 1  # 1 db_only + 0 broker_only


async def test_reconcile_filters_out_paper_positions_on_shared_credential(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One credential backs both paper and live strategies. Each has
    an open position. Broker reports only the live one. Without the
    Strategy.is_paper join filter, the paper position would surface as
    false db_only drift."""
    user, cred = await _seed_user_and_credential(db)
    live_strat = _make_strategy(user.id, cred.id, is_paper=False, name="live")
    paper_strat = _make_strategy(user.id, cred.id, is_paper=True, name="paper")
    db.add(live_strat)
    db.add(paper_strat)
    await db.flush()
    # Live position — broker should match.
    db.add(
        StrategyPosition(
            user_id=user.id,
            strategy_id=live_strat.id,
            broker_credential_id=cred.id,
            symbol="NIFTY",
            side="buy",
            total_quantity=1,
            remaining_quantity=1,
            avg_entry_price=Decimal("22500.0"),
            status="open",
        )
    )
    # Paper position — must NOT count as drift.
    db.add(
        StrategyPosition(
            user_id=user.id,
            strategy_id=paper_strat.id,
            broker_credential_id=cred.id,
            symbol="BANKNIFTY",
            side="sell",
            total_quantity=15,
            remaining_quantity=15,
            avg_entry_price=Decimal("48000.0"),
            status="open",
        )
    )
    await db.commit()

    _stub_broker_class(
        monkeypatch,
        positions=[
            Position(
                symbol="NIFTY",
                exchange=Exchange.NFO,
                quantity=1,
                avg_price=Decimal("22500.0"),
                ltp=Decimal("22510.0"),
                unrealized_pnl=Decimal("100.0"),
                product_type=ProductType.MARGIN,
            )
        ],
    )

    mismatches = await reconcile_once(db)
    assert mismatches == 0  # paper position correctly excluded
