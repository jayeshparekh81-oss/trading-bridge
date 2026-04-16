"""Async SQLAlchemy engine + session factory.

Exposes a single engine per process, lazily constructed from
:func:`app.core.config.get_settings`. The FastAPI dependency
:func:`get_session` yields an :class:`AsyncSession` bound to that engine
and guarantees cleanup even on exceptions.

Design notes:
    * ``expire_on_commit=False`` — we return ORM objects from handlers
      after ``commit()``; re-loading attributes off a closed session would
      raise. The services own transactional boundaries explicitly.
    * Engine is cached with :func:`functools.lru_cache` so tests can swap
      the DB URL by calling :func:`dispose_engine` first.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine.

    The engine is lazy — instantiating it does not open a connection, so
    this is safe to call from module scope.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide :class:`async_sessionmaker`."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a session and closes it on exit.

    Transactions are the caller's responsibility: services call
    ``await session.commit()`` or ``await session.rollback()`` explicitly.
    On unhandled exception the ``async with`` block rolls back.
    """
    maker = get_sessionmaker()
    async with maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close all connections and drop the cached engine.

    Called from the FastAPI lifespan shutdown and from tests that need to
    rebuild the engine against a different URL.
    """
    if get_engine.cache_info().currsize > 0:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


__all__ = ["dispose_engine", "get_engine", "get_session", "get_sessionmaker"]
