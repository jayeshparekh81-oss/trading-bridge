"""Test fixtures for the ``historical_candles`` service tests.

Pattern: per-test postgres session with rollback. Hooks into the real
local dev Postgres (already running, already at migration head
``029_historical_candles``) rather than aiosqlite — repository tests
exercise PostgreSQL-specific syntax (``pg_insert(...).on_conflict_do_nothing``)
that sqlite cannot replicate.

Each test gets a session inside a transaction; rollback at fixture
teardown discards every write so tests are isolated from each other
and from the dev seed data. No test should call ``session.commit()``.

A per-fixture random ``test_symbol_prefix`` is also exported so tests
can scope their writes to a unique namespace — defensive against the
rare case where a test does accidentally commit.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import dispose_engine, get_sessionmaker


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Per-test transactional postgres session. Rolls back AND disposes
    the engine at end of test. SKIPS gracefully when Postgres is
    unreachable (typical CI runners without a Postgres service).

    Probes connectivity with ``SELECT 1`` before yielding. Locally
    inside ``docker compose`` the probe succeeds and the test runs
    against the live dev Postgres. In CI without a Postgres service
    the probe raises and the test is marked SKIPPED. Matches the
    pre-030 pattern used in ``test_jobs_repository.py`` before its
    module-level pytestmark was lifted.

    The disposal is load-bearing: ``get_sessionmaker()`` caches a
    singleton engine, but pytest-asyncio creates a fresh event loop per
    test by default. Re-using the cached engine across loops triggers
    ``RuntimeError: ... attached to a different loop``. Calling
    :func:`dispose_engine` clears the LRU cache + closes the connection
    pool, so the next test gets a fresh engine bound to its own loop.

    Implementation notes:
      * Uses the same ``get_sessionmaker()`` the prod code does, so the
        connection string + pool settings match production.
      * ``try/finally`` guarantees rollback + dispose even when a test
        raises mid-assertion — keeps the dev DB pristine.
    """
    maker = get_sessionmaker()
    session = maker()
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        await session.close()
        await dispose_engine()
        pytest.skip(f"Postgres unreachable: {exc.__class__.__name__}: {exc}")
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await dispose_engine()


@pytest_asyncio.fixture
def test_symbol_prefix() -> str:
    """Unique symbol namespace for one test run.

    Concatenate with bar-specific suffixes when constructing ORM
    instances so leftover rows (from a hypothetical commit slip) never
    masquerade as production data.
    """
    return f"TEST_HC_{uuid.uuid4().hex[:8].upper()}"
