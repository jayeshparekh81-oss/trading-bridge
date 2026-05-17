"""Token-bucket rate limiting for ``POST /api/backtest``.

Protects the dormant backtest endpoint from runaway customer requests
when the router is registered. Two limits enforced together:

  1. Per-hour cap (default 30/hour/user) — fixed-window counter
     using the existing ``app.core.redis_client.rate_limit_check``
     helper.
  2. Concurrent cap (default 5 in-flight per user) — uses a Redis
     INCR/DECR pair scoped to the user's ``running`` slot count.

When EITHER limit is exceeded, the endpoint returns HTTP 429 with a
``Retry-After`` header. The middleware is opt-in: only mounted on
``POST /api/backtest`` (not on GET endpoints — read paths are cheap).

Configuration via env vars (with defaults):
    ``BACKTEST_RATE_LIMIT_PER_HOUR``     int, default 30
    ``BACKTEST_RATE_LIMIT_CONCURRENT``   int, default 5

The concurrent slot's release happens in the Celery task's final
``status → SUCCEEDED|FAILED`` transition (decrement counter).

Anonymous-config preview (future Day-6 work): defaults of 10/hour and
1 concurrent, keyed by IP rather than user_id.
"""

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_current_active_user
from app.core import redis_client
from app.core.logging import get_logger
from app.db.models.user import User

_logger = get_logger("app.backtest_extension.rate_limit")


# ─── Config ─────────────────────────────────────────────────────────────


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return max(1, v)
    except ValueError:
        _logger.warning(
            "rate_limit.config.invalid_env",
            name=name,
            raw_value=raw,
            using_default=default,
        )
        return default


PER_HOUR_LIMIT: int = _env_int("BACKTEST_RATE_LIMIT_PER_HOUR", 30)
CONCURRENT_LIMIT: int = _env_int("BACKTEST_RATE_LIMIT_CONCURRENT", 5)

#: Cache window in seconds (1 hour = 3600). Matches the per-hour cap
#: name; if BACKTEST_RATE_LIMIT_PER_HOUR is renamed, the window stays.
_PER_HOUR_WINDOW_SECONDS: int = 3600


# ─── Keys ───────────────────────────────────────────────────────────────


def _user_hourly_key(user_id: uuid.UUID) -> str:
    return f"backtest:per_hour:{user_id}"


def _user_concurrent_key(user_id: uuid.UUID) -> str:
    return f"backtest:concurrent:{user_id}"


# ─── Public API ─────────────────────────────────────────────────────────


class RateLimitExceededError(HTTPException):
    """Raised when a backtest request exceeds the rate limit.

    Carries an ``Retry-After`` header in seconds. Distinct from
    plain HTTPException so callers can identify rate-limit-specific
    failures in logs.
    """

    def __init__(self, *, kind: str, retry_after_seconds: int) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Backtest rate limit exceeded ({kind}). "
                f"Retry in {retry_after_seconds} seconds."
            ),
            headers={"Retry-After": str(retry_after_seconds)},
        )
        self.kind = kind
        self.retry_after_seconds = retry_after_seconds


async def check_request_rate(
    user_id: uuid.UUID,
    *,
    redis: redis_client.aioredis.Redis | None = None,
) -> None:
    """Hourly cap. Raises RateLimitExceededError(kind="per_hour") on breach.

    Uses the existing ``rate_limit_check`` helper which does INCR + EXPIRE
    in a single pipeline. Lightweight enough for every request.
    """
    allowed = await redis_client.rate_limit_check(
        _user_hourly_key(user_id),
        max_requests=PER_HOUR_LIMIT,
        window_seconds=_PER_HOUR_WINDOW_SECONDS,
        redis_client=redis,
    )
    if not allowed:
        raise RateLimitExceededError(
            kind="per_hour",
            retry_after_seconds=_PER_HOUR_WINDOW_SECONDS,
        )


async def acquire_concurrent_slot(
    user_id: uuid.UUID,
    *,
    redis: redis_client.aioredis.Redis | None = None,
) -> None:
    """Concurrent cap. Raises RateLimitExceededError(kind="concurrent") on breach.

    INCRs the concurrent counter. If post-INCR value > CONCURRENT_LIMIT,
    rolls back via DECR + raises 429.

    The caller MUST call ``release_concurrent_slot`` after the backtest
    completes (success OR failure) to return the slot. The Celery task's
    terminal-state transition handles this.

    A safety TTL is set on the key so abandoned slots eventually expire
    (in case the worker crashes between INCR and DECR).
    """
    client = redis or redis_client.get_redis()
    key = _user_concurrent_key(user_id)
    pipe = client.pipeline(transaction=False)
    pipe.incr(key)
    # 1-hour safety TTL — abandoned slots auto-release after the window
    pipe.expire(key, 3600)
    new_value, _ = await pipe.execute()
    if int(new_value) > CONCURRENT_LIMIT:
        # Roll back the INCR
        await client.decr(key)
        raise RateLimitExceededError(
            kind="concurrent",
            retry_after_seconds=60,  # short retry — slot might free up
        )


async def release_concurrent_slot(
    user_id: uuid.UUID,
    *,
    redis: redis_client.aioredis.Redis | None = None,
) -> None:
    """Release a concurrent slot — called after backtest terminates.

    Idempotent: if the counter is already 0 (or the key has expired),
    decrement is a no-op + the key is preserved so future INCR-cycles
    work correctly.
    """
    client = redis or redis_client.get_redis()
    key = _user_concurrent_key(user_id)
    new_value = await client.decr(key)
    if int(new_value) < 0:
        # Shouldn't normally happen — defensive correction.
        await client.set(key, 0)
        _logger.warning(
            "rate_limit.concurrent.over_decrement",
            user_id=str(user_id),
        )


# ─── FastAPI dependency ─────────────────────────────────────────────────


async def enforce_backtest_rate_limit(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """FastAPI dependency: enforces both per-hour AND concurrent caps.

    Mount on POST /api/backtest only:

        @router.post("/", dependencies=[Depends(enforce_backtest_rate_limit)])

    Returns the authenticated User (drop-in replacement for
    ``get_current_active_user``) so handlers can still use it as a
    body-arg dependency without double-resolving.

    On breach: HTTP 429 with Retry-After header.

    **Fail-open behaviour:** when no Redis client is available on
    ``request.app.state.redis`` (e.g. test harness without lifespan
    startup), the limiter logs a warning and lets the request through.
    Production always has the lifespan-initialised client, so this
    fallback only fires in dev/test paths.
    """
    user_id = current_user.id
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        _logger.warning(
            "rate_limit.no_redis.fail_open",
            user_id=str(user_id),
            note="No Redis on app.state — rate limit skipped (dev/test fallback)",
        )
        return current_user

    # 1. Per-hour cap (cheap; runs first)
    await check_request_rate(user_id, redis=redis)

    # 2. Concurrent cap (slightly more expensive but still 2 Redis ops)
    await acquire_concurrent_slot(user_id, redis=redis)

    # NOTE: the slot is RELEASED by the Celery task on terminal state.
    # If the handler returns 4xx/5xx before queuing the task, the slot
    # is leaked until the 1-hour safety TTL expires. Day 6 work can add
    # try/except in the handler to release on error.
    return current_user


__all__ = [
    "CONCURRENT_LIMIT",
    "PER_HOUR_LIMIT",
    "RateLimitExceededError",
    "acquire_concurrent_slot",
    "check_request_rate",
    "enforce_backtest_rate_limit",
    "release_concurrent_slot",
]
