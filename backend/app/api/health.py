"""Health endpoints.

Three probes for three audiences:

* ``/health`` — process is alive. Kubernetes liveness probe hits this.
* ``/health/ready`` — DB + Redis reachable. Readiness probe.
* ``/health/detailed`` — plus per-dependency latency. Intended for admin
  dashboards and on-call triage — wire up auth when the user router lands.

Probes never raise; they catch every exception so a broken dependency
reports a structured "degraded" instead of surfacing a 500 that would
page the wrong team.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.logging import get_logger

logger = get_logger("app.api.health")

router = APIRouter(prefix="/health", tags=["health"])


# ═══════════════════════════════════════════════════════════════════════
# /health — liveness
# ═══════════════════════════════════════════════════════════════════════


@router.get("")
@router.get("/")
async def liveness() -> dict[str, str]:
    """Cheapest possible liveness check — no I/O at all.

    The Kubernetes liveness probe needs a sub-millisecond response; the
    moment we touch Postgres here, a flaky DB restarts the pod.
    """
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════
# /health/ready — readiness
# ═══════════════════════════════════════════════════════════════════════


@router.get("/ready")
async def readiness(request: Request) -> dict[str, Any]:
    """Confirm DB + Redis are reachable before accepting traffic."""
    db_ok, _db_ms = await _check_db(request)
    redis_ok, _redis_ms = await _check_redis(request)
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    }


# ═══════════════════════════════════════════════════════════════════════
# /health/detailed — diagnostics
# ═══════════════════════════════════════════════════════════════════════


@router.get("/detailed")
async def detailed(request: Request) -> dict[str, Any]:
    """Readiness + per-dependency latency in ms.

    Exposed on the same router for simplicity; protect behind an admin
    guard once the auth layer lands (Step 6+).
    """
    db_ok, db_ms = await _check_db(request)
    redis_ok, redis_ms = await _check_redis(request)
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "db": {"ok": db_ok, "latency_ms": db_ms},
        "redis": {"ok": redis_ok, "latency_ms": redis_ms},
    }


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


async def _check_db(request: Request) -> tuple[bool, float | None]:
    """Run a ``SELECT 1`` and report latency. Failures return (False, None)."""
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        return False, None
    started = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — probe never raises
        logger.warning("health.db_failed", error=str(exc))
        return False, None
    return True, round((time.perf_counter() - started) * 1000, 3)


async def _check_redis(request: Request) -> tuple[bool, float | None]:
    """PING Redis and report latency. Failures return (False, None)."""
    client = getattr(request.app.state, "redis", None)
    if client is None:
        return False, None
    started = time.perf_counter()
    try:
        pong = await client.ping()
    except Exception as exc:  # noqa: BLE001 — probe never raises
        logger.warning("health.redis_failed", error=str(exc))
        return False, None
    if not pong:
        return False, None
    return True, round((time.perf_counter() - started) * 1000, 3)


__all__ = ["router"]
