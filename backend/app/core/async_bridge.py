"""Sync→async bridge for Celery workers: one persistent event loop per process.

Celery's prefork workers are synchronous. Each task wraps its coroutine through
:func:`run_async` so the async pipeline (DB + Redis + broker HTTP) runs to
completion from sync task code.

Why a *persistent* loop (incident 2026-05-24)
---------------------------------------------
The earlier per-module ``_run`` helpers created a NEW event loop for every task
(``asyncio.run`` or ``new_event_loop()`` + ``close()``). But the process-wide
cached clients —

    * :func:`app.core.redis_client.get_redis`                  (``@lru_cache``)
    * :func:`app.db.session.get_engine` / ``get_sessionmaker`` (``@lru_cache``)

bind their connections to the FIRST loop they touch. Once that loop closed, the
next task reused connections attached to a dead loop and raised
``RuntimeError: Event loop is closed`` / "Future attached to a different loop"
on roughly every other task (~50% failure — observed on ``check_market_status``
and reproducible on the signal-execution path).

Reusing ONE loop per worker process keeps those cached connections bound to a
loop that never closes between tasks, so they stay valid for the life of the
process. asyncpg / redis connection teardown then only happens at process exit,
not mid-life on a closing loop.

Fork safety
-----------
The loop is created lazily on first use, so it lives in the forked CHILD and is
never inherited from the prefork parent (which never executes tasks). A PID
guard recreates the loop if a fork ever inherits a stale one.

Serial execution
-----------------
Celery is configured ``worker_prefetch_multiplier=1`` and the prefork pool runs
one task at a time per child process, so :func:`run_async` is never re-entered
concurrently on the same persistent loop. If the pool model ever changes to a
threaded/gevent worker, this assumption must be revisited.

Test path
---------
When a loop is already running (eager tasks under FastAPI ``TestClient`` /
pytest-asyncio) we cannot call ``run_until_complete`` on it, so we offload to a
short-lived helper thread that owns its own loop — the behaviour the existing
integration suite already relies on.
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any

_loop_lock = threading.Lock()
_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_pid: int | None = None


def _get_persistent_loop() -> asyncio.AbstractEventLoop:
    """Return the per-process persistent event loop, creating it on first use.

    Lazy + PID-guarded so a forked child never drives a loop inherited from the
    prefork parent.
    """
    global _worker_loop, _worker_loop_pid
    pid = os.getpid()
    with _loop_lock:
        if _worker_loop is None or _worker_loop.is_closed() or _worker_loop_pid != pid:
            _worker_loop = asyncio.new_event_loop()
            _worker_loop_pid = pid
        return _worker_loop


def _run_in_helper_thread(coro: Any) -> Any:
    """Run *coro* in a fresh thread that owns its own loop (running-loop path)."""
    result_holder: dict[str, Any] = {}

    def _target() -> None:
        loop = asyncio.new_event_loop()
        try:
            result_holder["value"] = loop.run_until_complete(coro)
        except BaseException as exc:
            result_holder["error"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_target)
    thread.start()
    thread.join()
    if "error" in result_holder:
        raise result_holder["error"]
    return result_holder.get("value")


def run_async(coro: Any) -> Any:
    """Run *coro* to completion from a synchronous Celery task.

    * Production (no running loop): reuse the per-process persistent loop so
      cached Redis/DB connections stay bound to a live loop across tasks.
    * Tests (a loop is already running): offload to a helper thread with its
      own loop, since ``run_until_complete`` cannot drive an already-running
      loop on the same thread.
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None and running.is_running():
        return _run_in_helper_thread(coro)

    return _get_persistent_loop().run_until_complete(coro)


__all__ = ["run_async"]
