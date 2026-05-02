"""Runtime tests for :mod:`app.workers.position_loop`.

These tests bypass FastAPI's :class:`TestClient` deliberately. The
conftest's ``client`` fixture monkeypatches ``start_position_loop`` to
a no-op (Task #5: the loop ran in TestClient's event loop and raced
the seed for the StaticPool's single connection). Production runs in
uvicorn's single event loop where that race doesn't exist — these
tests reproduce that single-loop topology by spawning the loop
directly in pytest-asyncio's event loop with no TestClient in sight.

Coverage targets:

* ``start_position_loop`` actually creates a task and stores it on
  ``app.state.position_loop_task`` (smoke).
* ``run_once`` returns the outcome count and does not raise on an
  empty positions table (positive happy path).
* A tick that raises does NOT kill the loop — the next tick runs.
  Pins the inner-try-except contract so a contributor can't quietly
  let exceptions escape.
* ``stop_position_loop`` cancels cleanly and the task ends in the
  cancelled state.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.workers.position_loop import (
    _run_loop,
    run_once,
    start_position_loop,
    stop_position_loop,
)


# ═══════════════════════════════════════════════════════════════════════
# Test 1 — start_position_loop creates a task on app.state
# ═══════════════════════════════════════════════════════════════════════


class TestStartPositionLoop:
    @pytest_asyncio.fixture
    async def fresh_app(self) -> FastAPI:
        return FastAPI()

    async def test_start_creates_task_stored_on_app_state(
        self,
        fresh_app: FastAPI,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Smoke: ``start_position_loop`` schedules an asyncio.Task and
        attaches it to ``app.state.position_loop_task``. The task is in a
        not-yet-done state until either the loop body completes (never,
        in production) or :func:`stop_position_loop` cancels it.
        """
        # Route the loop's get_sessionmaker() at our test engine so the
        # task — once it starts ticking — doesn't blow up on missing engine.
        monkeypatch.setattr(
            "app.db.session.get_sessionmaker", lambda: db_session_maker
        )

        task = start_position_loop(fresh_app)

        try:
            assert isinstance(task, asyncio.Task)
            assert fresh_app.state.position_loop_task is task
            assert not task.done()
        finally:
            await stop_position_loop(fresh_app)


# ═══════════════════════════════════════════════════════════════════════
# Test 2 — run_once returns outcome count and doesn't raise empty
# ═══════════════════════════════════════════════════════════════════════


class TestRunOnce:
    async def test_empty_positions_table_returns_zero(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        """No open positions → tick returns 0 outcomes, no exception."""
        async with db_session_maker() as session:
            result = await run_once(session)

        assert result == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 3 — tick exceptions don't kill the loop
# ═══════════════════════════════════════════════════════════════════════


class TestTickFailureSurvival:
    async def test_failed_tick_does_not_kill_loop(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A tick that raises is logged and the loop sleeps + tries again.

        Strategy:

        * Replace ``manage_open_positions`` with a counter-tracking
          callable that raises on call #1, succeeds on call #2+.
        * Replace ``asyncio.sleep`` (as imported by ``position_loop``)
          with a no-op so the loop iterates at memory speed instead of
          the configured 5 s.
        * Spawn ``_run_loop`` as a task, yield until the counter shows
          at least 2 calls, assert the task is still running.

        Pins the contract that the inner try/except catches all
        exceptions and the outer try only exits on cancellation.
        """
        monkeypatch.setattr(
            "app.db.session.get_sessionmaker", lambda: db_session_maker
        )

        # Make the inter-tick sleep instant so we can test failure recovery
        # without burning real seconds. Same pattern pytest-asyncio docs
        # suggest for testing time-driven loops.
        # Patch the position_loop's own ``_sleep`` indirection — NOT
        # ``asyncio.sleep`` directly — so the test's own ``asyncio.sleep(0)``
        # yields work normally. Without this distinction, mocking
        # ``asyncio.sleep`` globally turns ``await asyncio.sleep(0)`` into
        # ``await None`` and the event loop never schedules the loop task.
        monkeypatch.setattr(
            "app.workers.position_loop._sleep",
            AsyncMock(return_value=None),
        )

        call_count = {"value": 0}

        async def _flaky_manage(_session: AsyncSession) -> list[Any]:
            call_count["value"] += 1
            if call_count["value"] == 1:
                raise RuntimeError("simulated tick failure")
            # Return one opaque outcome so the loop hits the
            # ``if outcomes`` truthy branches (run_once.commit and the
            # ``position_loop.tick`` info log) — covers the otherwise-
            # only-on-real-positions paths.
            return [{"opaque": "outcome"}]

        monkeypatch.setattr(
            "app.services.position_manager.manage_open_positions",
            _flaky_manage,
        )

        task = asyncio.create_task(_run_loop(), name="test-position-loop")
        try:
            # Yield enough times for the loop to run at least 2 ticks.
            # Each tick has ~3 awaits (session ctx, run_once, sleep);
            # 20 yields is conservative.
            for _ in range(20):
                await asyncio.sleep(0)
                if call_count["value"] >= 2:
                    break

            assert call_count["value"] >= 2, (
                f"Expected loop to retry after failure; got "
                f"{call_count['value']} call(s) total — the failed tick "
                f"may have killed the loop."
            )
            assert not task.done(), (
                f"Loop task ended unexpectedly after a failed tick; "
                f"exception={task.exception() if task.done() else None}"
            )
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


# ═══════════════════════════════════════════════════════════════════════
# Test 4 — clean shutdown via stop_position_loop
# ═══════════════════════════════════════════════════════════════════════


class TestStopPositionLoop:
    async def test_stop_cancels_task_cleanly(
        self,
        db_session_maker: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """:func:`stop_position_loop` cancels the task and awaits it.

        After the call:
        * ``task.done()`` is True.
        * ``task.cancelled()`` is True (loop's outer ``try`` re-raises
          ``CancelledError`` after logging — the standard graceful
          shutdown signal).
        * No unhandled exception leaked.
        """
        monkeypatch.setattr(
            "app.db.session.get_sessionmaker", lambda: db_session_maker
        )
        # Patch the position_loop's own ``_sleep`` indirection — NOT
        # ``asyncio.sleep`` directly — so the test's own ``asyncio.sleep(0)``
        # yields work normally. Without this distinction, mocking
        # ``asyncio.sleep`` globally turns ``await asyncio.sleep(0)`` into
        # ``await None`` and the event loop never schedules the loop task.
        monkeypatch.setattr(
            "app.workers.position_loop._sleep",
            AsyncMock(return_value=None),
        )

        app = FastAPI()
        task = start_position_loop(app)

        # Let the loop tick at least once so we're not just cancelling
        # an unstarted task — that would test nothing.
        for _ in range(5):
            await asyncio.sleep(0)

        await stop_position_loop(app)

        assert task.done()
        assert task.cancelled()

    async def test_stop_is_idempotent_when_never_started(self) -> None:
        """Calling stop on an app that never started the loop is a no-op,
        not an error. Important so shutdown handlers can call this
        unconditionally even if startup bailed before the loop spawned.
        """
        app = FastAPI()
        # No start_position_loop call. app.state.position_loop_task is unset.
        await stop_position_loop(app)  # must not raise
