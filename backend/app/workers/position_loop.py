"""Position-manager background loop.

Runs as an asyncio task spawned from FastAPI's lifespan. Calls
:func:`app.services.position_manager.manage_open_positions` on a fixed
interval, owning its own DB session per tick so a slow broker call
doesn't hold a request-scoped session open.

The loop is a no-op when ``settings.strategy_paper_mode`` is True — the
position-manager itself short-circuits, but we also widen the sleep here
to avoid burning CPU for a thousand-row poll that immediately returns.

Lifecycle:
    * Started by ``main.lifespan`` after the DB engine + Redis are up.
    * Cancelled cleanly on shutdown — the loop catches CancelledError
      and exits without committing partial work.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

_logger = get_logger("workers.position_loop")

#: Module-level indirection for the inter-tick sleep. Tests monkeypatch
#: this to a no-op so the failure-survival / shutdown checks complete in
#: milliseconds without affecting global ``asyncio.sleep`` (which the
#: test itself calls to yield to the event loop).
_sleep = asyncio.sleep


async def run_once(session: AsyncSession) -> int:
    """Execute exactly one tick of the loop body — the public test seam.

    Imported from :mod:`app.services.position_manager` lazily so a test
    that monkeypatches ``manage_open_positions`` reliably overrides the
    reference :func:`_run_loop` resolves at call time.

    Production code drives this from :func:`start_position_loop` inside a
    forever-loop with its own session and configurable sleep interval;
    tests drive it directly with a session of their choosing so the
    while/sleep/cancel machinery is exercised separately.

    Returns the number of position outcomes processed in this tick. The
    caller (or the production loop) owns commit-and-log on a non-zero
    count — keeping the tick body itself idempotent and side-effect-free
    beyond the session it was given.
    """
    from app.services.position_manager import manage_open_positions

    outcomes = await manage_open_positions(session)
    if outcomes:
        await session.commit()
    return len(outcomes)


async def _run_loop() -> None:
    """Forever-loop driver — opens one session per tick, calls :func:`run_once`.

    Per-tick errors are swallowed and logged so a transient broker /
    Postgres blip does not kill the worker. ``CancelledError`` is the
    only path out — surfaced from :func:`stop_position_loop` on shutdown.
    """
    settings = get_settings()
    interval = (
        settings.strategy_position_poll_seconds
        if not settings.strategy_paper_mode
        else max(settings.strategy_position_poll_seconds, 30)
    )

    from app.db.session import get_sessionmaker

    maker = get_sessionmaker()
    _logger.info(
        "position_loop.started",
        interval=interval,
        paper_mode=settings.strategy_paper_mode,
    )
    try:
        while True:
            try:
                async with maker() as session:
                    outcomes = await run_once(session)
                    if outcomes:
                        _logger.info(
                            "position_loop.tick", outcomes=outcomes
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _logger.warning(
                    "position_loop.tick_failed", error=str(exc)
                )
            await _sleep(interval)
    except asyncio.CancelledError:
        _logger.info("position_loop.cancelled")
        raise


def start_position_loop(app: FastAPI) -> asyncio.Task[None]:
    """Spawn the loop on FastAPI startup. Returns the task so lifespan can cancel it."""
    task = asyncio.create_task(_run_loop(), name="position_loop")
    app.state.position_loop_task = task
    return task


async def stop_position_loop(app: FastAPI) -> None:
    """Cancel and await the loop. Idempotent — safe to call if never started."""
    task: asyncio.Task[None] | None = getattr(app.state, "position_loop_task", None)
    if task is None or task.done():
        return
    import contextlib

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


__all__ = ["run_once", "start_position_loop", "stop_position_loop"]
