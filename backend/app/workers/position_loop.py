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

_logger = get_logger("workers.position_loop")


async def _run_loop() -> None:
    """The actual loop body — kept private so tests drive it via ``run_once``."""
    settings = get_settings()
    interval = (
        settings.strategy_position_poll_seconds
        if not settings.strategy_paper_mode
        else max(settings.strategy_position_poll_seconds, 30)
    )

    from app.db.session import get_sessionmaker
    from app.services.position_manager import manage_open_positions

    maker = get_sessionmaker()
    _logger.info("position_loop.started", interval=interval, paper_mode=settings.strategy_paper_mode)
    try:
        while True:
            try:
                async with maker() as session:
                    outcomes = await manage_open_positions(session)
                    if outcomes:
                        await session.commit()
                        _logger.info(
                            "position_loop.tick", outcomes=len(outcomes)
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _logger.warning(
                    "position_loop.tick_failed", error=str(exc)
                )
            await asyncio.sleep(interval)
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


__all__ = ["start_position_loop", "stop_position_loop"]
