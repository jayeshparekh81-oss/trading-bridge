"""Beat task — expired-option paper square-off (Options Brick #4, slice ②).

Thin celery wrapper over :func:`app.services.options_expiry_sweep.
sweep_expired_options`. Runs on the async_bridge persistent per-process loop
(the 2026-05-24 loop-incident pattern — see ``async_bridge``). Passes the
worker's in-process Dhan scrip master for master-first expiry derivation; a
cold/stale master just falls back to symbol parsing inside the sweep.

Dormant by default: the sweep itself gates on ``options_execution_enabled``
(False everywhere today) and returns without touching a row.
"""

from __future__ import annotations

from typing import Any

from app.core.async_bridge import run_async as _run
from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger("app.tasks.options_expiry_tasks")


async def _sweep() -> dict[str, Any]:
    from app.brokers.dhan import _SCRIP_MASTER
    from app.db.session import get_sessionmaker
    from app.services.options_expiry_sweep import sweep_expired_options

    maker = get_sessionmaker()
    async with maker() as session:
        return await sweep_expired_options(session, scrip_master=_SCRIP_MASTER)


@celery_app.task(
    name="app.tasks.options_expiry_tasks.sweep_expired_option_positions",
    max_retries=3,
    default_retry_delay=30,
)
def sweep_expired_option_positions() -> dict[str, Any]:
    """Beat-scheduled sweep; failures retry, then surface in worker logs."""
    result = _run(_sweep())
    logger.info("options_expiry_sweep.task_done", **result)
    return result
