"""Scrip-master warm task — keep the worker's in-process cache off the hot path.

The Dhan scrip-master (`app.brokers.dhan._SCRIP_MASTER`) is a per-process
in-memory cache with a 24h TTL. Without warming, the first F&O signal after
an expiry window pays a ~9s CSV download *inside the order-execution task*
(observed 2026-07-06: CDSL signal, web + worker both cache-missed after the
weekend gap).

Two consumers keep it warm:

* Beat schedule (see ``celery_app.py``) — daily pre-market (09:05 IST) plus
  every 6h, so the TTL never expires between market sessions.
* ``worker_process_init`` hook (also ``celery_app.py``) — each prefork child
  schedules a warm on its persistent loop at fork time (non-blocking; Celery
  kills init handlers that block >4s, and the download alone takes ~8s on
  EC2). The warm then runs alongside the child's first task.

Both execute on the async_bridge persistent per-process loop so the cache's
``asyncio.Lock`` binds to the same loop the execution tasks use (see
async_bridge docstring for the 2026-05-24 loop incident).
"""

from __future__ import annotations

import httpx

from app.core.async_bridge import run_async as _run
from app.core.config import get_settings
from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger("app.tasks.scrip_master_tasks")


async def warm() -> dict[str, int | str]:
    """Ensure the scrip-master is loaded; no-op when the TTL is still fresh."""
    from app.brokers.dhan import _SCRIP_MASTER

    settings = get_settings()
    async with httpx.AsyncClient() as http:
        await _SCRIP_MASTER.ensure_loaded(http, settings.dhan_scrip_master_url)
    entries = len(_SCRIP_MASTER._by_symbol)
    logger.info("worker.scrip_master.warmed", entries=entries)
    return {"status": "ok", "entries": entries}


@celery_app.task(
    name="app.tasks.scrip_master_tasks.warm_scrip_master",
    max_retries=3,
    default_retry_delay=30,
)
def warm_scrip_master() -> dict[str, int | str]:
    """Beat-scheduled warm; failures retry, then surface in worker logs only."""
    return _run(warm())
