"""Per-user live-trading combinator tests.

The combinator is the safety AND of the global ``LIVE_TRADING_ENABLED``
feature flag and the per-user ``users.live_trading_enabled`` column —
both must be true for live orders to be allowed. These tests pin every
edge case the live-orders SafetyChain depends on:

    * Global off + user off  → False.
    * Global off + user on   → False (global is the master kill-switch).
    * Global on  + user off  → False (per-user opt-in still required).
    * Global on  + user on   → True.
    * Unknown user_id        → False.
    * New user defaults      → False (the safe-default contract).
    * Global flag short-circuits before DB I/O.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models.user import User
from app.strategy_engine.feature_flags import reset_all_flags, set_flag
from app.strategy_engine.feature_flags.constants import ENV_PREFIX
from app.strategy_engine.live_orders.user_flags import (
    is_live_trading_enabled_for_user,
)


@pytest.fixture(autouse=True)
def _isolated_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Same isolation as ``test_feature_flags.py`` — drop every env
    override and runtime override before and after each test."""
    for name, _ in list(os.environ.items()):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name, raising=False)
    reset_all_flags()
    yield
    reset_all_flags()


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def user_off(db: AsyncSession) -> User:
    """Newly-created user — defaults to ``live_trading_enabled = False``."""
    u = User(email="off@x", password_hash="p", is_active=True)
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def user_on(db: AsyncSession) -> User:
    """User with the per-user opt-in explicitly turned on."""
    u = User(
        email="on@x",
        password_hash="p",
        is_active=True,
        live_trading_enabled=True,
    )
    db.add(u)
    await db.flush()
    return u


# ─── 1. New users default to False ────────────────────────────────────


@pytest.mark.asyncio
async def test_new_user_defaults_to_live_trading_disabled(
    user_off: User,
) -> None:
    assert user_off.live_trading_enabled is False


# ─── 2. AND combinator semantics ──────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_false_when_global_off_and_user_off(
    db: AsyncSession, user_off: User
) -> None:
    assert (
        await is_live_trading_enabled_for_user(db, user_off.id) is False
    )


@pytest.mark.asyncio
async def test_returns_false_when_global_off_but_user_on(
    db: AsyncSession, user_on: User
) -> None:
    """Global flag is the master kill-switch — overrides per-user opt-in."""
    assert (
        await is_live_trading_enabled_for_user(db, user_on.id) is False
    )


@pytest.mark.asyncio
async def test_returns_false_when_global_on_but_user_off(
    db: AsyncSession, user_off: User
) -> None:
    """Per-user opt-in is required even when the global flag is on."""
    set_flag("LIVE_TRADING_ENABLED", True)
    assert (
        await is_live_trading_enabled_for_user(db, user_off.id) is False
    )


@pytest.mark.asyncio
async def test_returns_true_when_both_on(
    db: AsyncSession, user_on: User
) -> None:
    set_flag("LIVE_TRADING_ENABLED", True)
    assert (
        await is_live_trading_enabled_for_user(db, user_on.id) is True
    )


# ─── 3. Unknown user id ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_user_id_returns_false(db: AsyncSession) -> None:
    set_flag("LIVE_TRADING_ENABLED", True)
    assert (
        await is_live_trading_enabled_for_user(db, uuid.uuid4()) is False
    )


# ─── 4. Global flag short-circuits before DB I/O ─────────────────────


@pytest.mark.asyncio
async def test_global_flag_off_short_circuits_db(
    db: AsyncSession, user_on: User
) -> None:
    """When the global flag is off, no DB query should execute.

    We monkey-patch the session's ``execute`` to raise; if the helper
    short-circuits correctly, the patched method is never called and
    the helper returns ``False`` cleanly.
    """

    async def _explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("DB should not be touched when global flag is off")

    db.execute = _explode  # type: ignore[method-assign]
    assert (
        await is_live_trading_enabled_for_user(db, user_on.id) is False
    )
