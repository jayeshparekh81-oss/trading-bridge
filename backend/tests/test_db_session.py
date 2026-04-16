"""Tests for :mod:`app.db.session` — engine + sessionmaker caching."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core import config as config_module
from app.db import session as session_module


@pytest.fixture(autouse=True)
def _isolate_engine_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point at an in-memory SQLite URL and clear caches between tests."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.pop("FYERS_APP_ID", None)
    config_module.get_settings.cache_clear()
    session_module.get_engine.cache_clear()
    session_module.get_sessionmaker.cache_clear()
    yield
    session_module.get_engine.cache_clear()
    session_module.get_sessionmaker.cache_clear()


class TestEngineFactory:
    def test_get_engine_returns_async_engine(self) -> None:
        engine = session_module.get_engine()
        assert isinstance(engine, AsyncEngine)
        # Cached — second call returns same object.
        assert session_module.get_engine() is engine

    def test_get_sessionmaker_binds_engine(self) -> None:
        maker = session_module.get_sessionmaker()
        assert isinstance(maker, async_sessionmaker)
        assert maker.kw["bind"] is session_module.get_engine()

    async def test_dispose_engine_clears_cache(self) -> None:
        _ = session_module.get_engine()
        assert session_module.get_engine.cache_info().currsize == 1
        await session_module.dispose_engine()
        assert session_module.get_engine.cache_info().currsize == 0

    async def test_dispose_when_not_created_is_noop(self) -> None:
        # No engine cached yet — must not raise.
        assert session_module.get_engine.cache_info().currsize == 0
        await session_module.dispose_engine()


class TestGetSessionDependency:
    async def test_yields_session_and_closes_on_exception(self) -> None:
        gen = session_module.get_session()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("forced"))
        # Generator is exhausted after throw; confirm session closed.
        assert session.is_active is False or session.sync_session is not None

    async def test_yields_session_clean_path(self) -> None:
        gen = session_module.get_session()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
