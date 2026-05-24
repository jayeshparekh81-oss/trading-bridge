"""Regression tests for the Celery sync→async bridge (incident 2026-05-24).

Root cause being guarded against: the old per-module ``_run`` helpers created a
NEW event loop for every task (``asyncio.run`` / ``new_event_loop`` + close).
The process-wide ``@lru_cache`` clients (``get_redis``, ``get_engine`` /
``get_sessionmaker``) bind their connections to the FIRST loop they touch, so
the next task reused connections attached to a dead loop and raised
``RuntimeError: Event loop is closed`` / "Future attached to a different loop"
on ~every other task.

The fix (:func:`app.core.async_bridge.run_async`) reuses ONE persistent loop per
worker process. ``test_sequential_calls_on_loop_bound_resource_all_succeed``
below is the unit-level form of the 6-call container reproduction that FAILED on
call 2 before the fix.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core import async_bridge
from app.core.async_bridge import run_async


class _LoopBoundResource:
    """Mimics a redis/DB singleton: binds to the loop of its first use and
    fails on any later loop — exactly the asyncpg / redis.asyncio failure mode
    that produced "Event loop is closed" in production.
    """

    def __init__(self) -> None:
        self._bound_loop: asyncio.AbstractEventLoop | None = None

    async def use(self) -> int:
        current = asyncio.get_running_loop()
        if self._bound_loop is None:
            self._bound_loop = current
        elif self._bound_loop is not current:
            # Same symptom the cached connections raised across loops.
            raise RuntimeError("Event loop is closed")
        return 1


# ─────────────────────────────────────────────────────────────────────────
# Core fix: persistent loop reused across sequential (sync-worker) calls
# ─────────────────────────────────────────────────────────────────────────


def test_sequential_calls_on_loop_bound_resource_all_succeed() -> None:
    """The 6-sequential-call reproduction. Pre-fix this failed on call 2 with
    "Event loop is closed"; with a persistent loop all calls share one loop."""
    resource = _LoopBoundResource()
    results = [run_async(resource.use()) for _ in range(6)]
    assert results == [1] * 6


def test_run_async_reuses_a_single_loop() -> None:
    """Every sync-path call runs on the same loop object (pre-fix: a new loop
    per call)."""
    seen: list[int] = []

    async def capture() -> None:
        seen.append(id(asyncio.get_running_loop()))

    for _ in range(5):
        run_async(capture())

    assert len(set(seen)) == 1


def test_run_async_returns_value_on_sync_path() -> None:
    async def work() -> str:
        return "done"

    assert run_async(work()) == "done"


def test_exception_propagates_on_sync_path() -> None:
    """execute_signal_async depends on exceptions surfacing so Celery can
    retry — the bridge must not swallow them."""

    async def boom() -> None:
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        run_async(boom())


def test_persistent_loop_recreated_if_closed() -> None:
    """A closed loop (e.g. after process-shutdown teardown) is transparently
    recreated rather than re-raising "Event loop is closed"."""

    async def one() -> int:
        return 1

    assert run_async(one()) == 1
    assert async_bridge._worker_loop is not None
    async_bridge._worker_loop.close()

    assert run_async(one()) == 1  # recreated, no error


# ─────────────────────────────────────────────────────────────────────────
# Running-loop path (eager tasks under pytest-asyncio / TestClient)
# ─────────────────────────────────────────────────────────────────────────


async def test_run_async_offloads_when_a_loop_is_running() -> None:
    """Inside a running loop, run_async offloads to a helper thread instead of
    calling run_until_complete on the active loop."""

    async def work() -> str:
        return "ok"

    assert run_async(work()) == "ok"


async def test_exception_propagates_on_helper_thread_path() -> None:
    async def boom() -> None:
        raise ValueError("thread-permanent")

    with pytest.raises(ValueError, match="thread-permanent"):
        run_async(boom())


# ─────────────────────────────────────────────────────────────────────────
# Invariants the fix relies on
# ─────────────────────────────────────────────────────────────────────────


def test_celery_prefetch_multiplier_is_one() -> None:
    """Serial per-process execution is what makes a single persistent loop
    safe (no concurrent run_until_complete on the same loop)."""
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.worker_prefetch_multiplier == 1


def test_all_task_modules_share_the_bridge() -> None:
    """signal_execution, kill_switch_tasks and notification_tasks must all
    delegate to the one shared helper — no divergent local copies."""
    import app.tasks.kill_switch_tasks as ks
    import app.tasks.notification_tasks as nt
    import app.tasks.signal_execution as se

    assert se._run is run_async
    assert ks._run is run_async
    assert nt._run is run_async
