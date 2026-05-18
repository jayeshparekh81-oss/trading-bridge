"""Per-strategy ``is_paper`` flag — overrides the global paper toggle.

Incident 2026-05-18: the global ``STRATEGY_PAPER_MODE`` flipped a live
strategy into paper mode, silently converting ~₹50–100k of real-money
fills into simulated ones. Migration 027 added
``strategies.is_paper`` and the executor / direct-exit / time-of-day
paths now resolve per-strategy via
:func:`app.services.paper_mode_resolver.resolve_paper_mode`.

These tests pin the resolver semantics. They are intentionally narrow:
unit-test the resolver in all four override combinations and a paper-
fill executor case to prove the wiring actually reaches the broker
decision point. The full executor end-to-end coverage (multi-leg rows,
position open, level computation) is already exercised by
``test_strategy_engine.py::test_executor_paper_mode_opens_position`` —
this file does NOT repeat it, only the per-strategy override behaviour.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio

# Ensure global paper mode is the default OFF starting point for tests
# that explicitly toggle it. Each test re-sets the env var it cares about.
os.environ.setdefault("STRATEGY_PAPER_MODE", "false")

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.schemas.broker import BrokerName
from app.services.paper_mode_resolver import resolve_paper_mode
from app.services.strategy_executor import place_strategy_orders


# ═══════════════════════════════════════════════════════════════════════
# Resolver — pure unit tests (no DB, no broker)
# ═══════════════════════════════════════════════════════════════════════


def _make_strategy(is_paper: bool | None) -> Strategy:
    """Build a Strategy instance in memory (not persisted)."""
    s = Strategy(
        name="resolver-test",
        broker_credential_id=None,
        entry_lots=4,
        partial_profit_lots=2,
        trail_lots=2,
        ai_validation_enabled=False,
        is_active=True,
    )
    # Bypass the ORM-side default so we can exercise None / True / False.
    s.is_paper = is_paper  # type: ignore[assignment]
    return s


def test_strategy_is_paper_false_overrides_global_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The founder's live strategy (is_paper=False) must stay LIVE even
    when the global flag is TRUE — the exact bug from 2026-05-18."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    strategy = _make_strategy(is_paper=False)
    assert resolve_paper_mode(strategy) is False


def test_strategy_is_paper_true_overrides_global_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A strategy explicitly marked paper must stay paper even when
    global is LIVE — guards against the inverse mistake (a user opts
    one strategy into paper testing on an otherwise-live deployment)."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()

    strategy = _make_strategy(is_paper=True)
    assert resolve_paper_mode(strategy) is True


def test_strategy_is_paper_null_falls_back_to_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Strategy with no explicit flag (None at the Python layer —
    legacy in-memory construction or a row predating the column)
    inherits the global ``settings.strategy_paper_mode``. Verifies
    both directions of the fallback."""
    strategy = _make_strategy(is_paper=None)

    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()
    assert resolve_paper_mode(strategy) is True

    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()
    assert resolve_paper_mode(strategy) is False


def test_legacy_strategies_without_flag_default_paper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defence-in-depth: if a Strategy is missing the ``is_paper``
    attribute entirely (e.g. partial-mock objects in old tests, or a
    cached row hydrated before migration 027 ran), the resolver MUST
    NOT raise AttributeError and MUST default to whatever the global
    fallback says. The safe baseline is paper (global=TRUE)."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    class _Bare:
        """Stand-in for a Strategy that pre-dates migration 027."""

    bare = _Bare()  # no ``is_paper`` attribute at all
    assert resolve_paper_mode(bare) is True  # type: ignore[arg-type]

    # When global is FALSE the bare object still falls back cleanly.
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()
    assert resolve_paper_mode(bare) is False  # type: ignore[arg-type]


def test_none_strategy_returns_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """A None strategy (no row resolved) is the safest fallback — global
    decides. This protects callers that pass strategy=None when a token
    fails to resolve."""
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()
    assert resolve_paper_mode(None) is True

    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()
    assert resolve_paper_mode(None) is False


# ═══════════════════════════════════════════════════════════════════════
# Integration — executor honours per-strategy flag, not global
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db: AsyncSession) -> dict[str, Any]:
    user = User(email="t@example.com", password_hash="x", is_active=True)
    db.add(user)
    await db.flush()

    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.FYERS,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SECRET"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred)
    await db.flush()

    strategy = Strategy(
        user_id=user.id,
        name="override-test",
        broker_credential_id=cred.id,
        entry_lots=4,
        partial_profit_lots=2,
        partial_profit_target_pct=Decimal("1.000"),
        trail_lots=2,
        trail_offset_pct=Decimal("0.500"),
        hard_sl_pct=Decimal("1.000"),
        ai_validation_enabled=False,
        is_active=True,
        is_paper=True,  # default; flipped per test
    )
    db.add(strategy)
    await db.flush()

    signal = StrategySignal(
        user_id=user.id,
        strategy_id=strategy.id,
        raw_payload={"price": "100"},
        symbol="NIFTY24500CE",
        action="BUY",
        quantity=4,
        order_type="market",
        status="received",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    await db.refresh(strategy)

    return {"strategy": strategy, "signal": signal, "credential": cred}


@pytest.mark.asyncio
async def test_executor_uses_per_strategy_flag_paper_overrides_live_global(
    db: AsyncSession,
    seeded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global flag=LIVE but strategy.is_paper=True → executor simulates fill.

    Asserts no broker factory was ever called. The strategy is marked
    paper, so even though the global says LIVE the executor must NOT
    reach the broker codepath.
    """
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()

    seeded["strategy"].is_paper = True

    def _factory(_creds: Any) -> Any:
        raise AssertionError(
            "broker factory must NOT be called in paper mode — the "
            "per-strategy flag failed to override the global setting."
        )

    result = await place_strategy_orders(
        db,
        signal=seeded["signal"],
        strategy=seeded["strategy"],
        broker_factory=_factory,
    )
    await db.commit()

    assert result.success
    assert result.paper_mode is True


@pytest.mark.asyncio
async def test_executor_uses_per_strategy_flag_live_overrides_paper_global(
    db: AsyncSession,
    seeded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global flag=PAPER but strategy.is_paper=False → executor attempts
    a live broker call.

    Detection trick: the supplied ``broker_factory`` raises a sentinel
    exception. If the executor was still consulting the global flag
    (=paper), it would never reach ``_build_broker`` and the factory
    would never fire — the test would surface a paper-fill ExecutionResult
    instead of the sentinel. Either side of the regression is caught.
    This is the exact behaviour that would have prevented the
    2026-05-18 incident.
    """
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    seeded["strategy"].is_paper = False

    class _SentinelFactoryFired(RuntimeError):
        """Raised from the broker factory — proves the live path ran."""

    def _factory(_creds: Any) -> Any:
        raise _SentinelFactoryFired("live path reached")

    with pytest.raises(_SentinelFactoryFired):
        await place_strategy_orders(
            db,
            signal=seeded["signal"],
            strategy=seeded["strategy"],
            broker_factory=_factory,
        )
