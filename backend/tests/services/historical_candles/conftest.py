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

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

import os

import pytest

from app.core import config as config_module
from app.db.session import dispose_engine, get_sessionmaker

#: The Postgres URL as it reads at COLLECTION time, before any test has had a
#: chance to mutate the environment. The module-level ``skipif`` probe in
#: test_repository.py / test_jobs_repository.py resolves the URL at collection
#: time too, so this is the URL the skip decision was actually made against.
_COLLECTION_TIME_DB_URL = config_module.get_settings().database_url


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Per-test transactional postgres session. Rolls back AND disposes
    the engine at end of test.

    The disposal is load-bearing: ``get_sessionmaker()`` caches a
    singleton engine, but pytest-asyncio creates a fresh event loop per
    test by default. Re-using the cached engine across loops triggers
    ``RuntimeError: ... attached to a different loop``. Calling
    :func:`dispose_engine` clears the LRU cache + closes the connection
    pool, so the next test gets a fresh engine bound to its own loop.

    Postgres-reachability is gated at the module level — see the
    ``pytestmark = pytest.mark.skipif(...)`` block at the top of
    ``test_jobs_repository.py`` and ``test_repository.py``. When the
    probe fails (CI without a live Postgres) every test in those modules
    is SKIPPED at collection time and this fixture never runs.

    Implementation notes:
      * Uses the same ``get_sessionmaker()`` the prod code does, so the
        connection string + pool settings match production.
      * ``try/finally`` guarantees rollback + dispose even when a test
        raises mid-assertion — keeps the dev DB pristine.
    """
    # PIN the URL for the duration.
    #
    # The skip gate is decided ONCE at collection time from get_settings(), but the
    # engine is resolved LATER from cached global state. Any earlier test that leaves
    # a sqlite DATABASE_URL in the settings cache therefore makes these tests run
    # against SQLite while the gate still says "Postgres reachable" — 24 tests then
    # fail on SQLite dialect errors, pass in isolation, and look like a code
    # regression. Pinning the URL back to what the skip decision was made against
    # makes the fixture immune to whatever ran before it.
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _COLLECTION_TIME_DB_URL
    config_module.get_settings.cache_clear()
    await dispose_engine()

    maker = get_sessionmaker()
    bound = str(maker.kw["bind"].url)
    if not bound.startswith("postgresql"):
        pytest.fail(
            f"historical_candles tests require Postgres but the engine bound to "
            f"{bound!r}. The URL was pinned to {_COLLECTION_TIME_DB_URL!r}; if this "
            "still fires, something re-resolved the engine mid-test.")

    session = maker()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await dispose_engine()
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        config_module.get_settings.cache_clear()


@pytest_asyncio.fixture
def test_symbol_prefix() -> str:
    """Unique symbol namespace for one test run.

    Concatenate with bar-specific suffixes when constructing ORM
    instances so leftover rows (from a hypothetical commit slip) never
    masquerade as production data.
    """
    return f"TEST_HC_{uuid.uuid4().hex[:8].upper()}"
