"""Redis helpers — caching, rate limiting, kill-switch state, idempotency.

All of the ``speed`` layer lives here: the webhook hot path consults Redis
for rate limiting, kill-switch status, and duplicate detection BEFORE it
touches Postgres. Keeping these primitives in one place means:

* One connection pool per process — no fan-out of ``redis.from_url`` calls.
* Key-naming convention is centralised (``cache:``, ``rate:``, ``kill:``,
  ``idem:``, ``pnl:``, ``pos:``) so ops teams know which namespace to
  target with ``FLUSHDB`` or ``SCAN`` in incidents.
* Timing-sensitive operations (rate limit, idempotency set) use pipelines
  so we round-trip once, not five times.

The module is connection-pool-singleton by default for the app, but every
public function accepts an explicit ``redis_client`` argument so tests can
inject a fake (``fakeredis.aioredis.FakeRedis``) without monkeypatching.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis


logger = get_logger("app.core.redis_client")


# ═══════════════════════════════════════════════════════════════════════
# Key namespaces — single source of truth
# ═══════════════════════════════════════════════════════════════════════

_NS_CACHE = "cache"
_NS_RATE = "rate"
_NS_KILL = "kill"
_NS_IDEM = "idem"
_NS_PNL = "pnl"
_NS_POS = "pos"


def _cache_key(key: str) -> str:
    return f"{_NS_CACHE}:{key}"


def _rate_key(key: str) -> str:
    return f"{_NS_RATE}:{key}"


def _kill_key(user_id: UUID | str) -> str:
    return f"{_NS_KILL}:{user_id}"


def _idem_key(signal_hash: str) -> str:
    return f"{_NS_IDEM}:{signal_hash}"


def _pnl_key(user_id: UUID | str) -> str:
    return f"{_NS_PNL}:{user_id}"


def _pos_key(user_id: UUID | str) -> str:
    return f"{_NS_POS}:{user_id}"


# ═══════════════════════════════════════════════════════════════════════
# Kill-switch status vocabulary
# ═══════════════════════════════════════════════════════════════════════

KILL_SWITCH_ACTIVE = "ACTIVE"
KILL_SWITCH_TRIPPED = "TRIPPED"


# ═══════════════════════════════════════════════════════════════════════
# Connection pool
# ═══════════════════════════════════════════════════════════════════════


@lru_cache(maxsize=1)
def get_redis() -> aioredis.Redis:
    """Return the process-wide async Redis client.

    Uses ``redis.asyncio.from_url`` which owns an internal connection pool —
    safe to share across asyncio tasks. ``decode_responses=True`` keeps
    every string operation ``str`` instead of ``bytes``, which matches the
    rest of this codebase.
    """
    import redis.asyncio as aioredis

    settings = get_settings()
    return aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis() -> None:
    """Close the cached Redis client — called from lifespan shutdown + tests."""
    if get_redis.cache_info().currsize > 0:
        client = get_redis()
        await client.aclose()
    get_redis.cache_clear()


# ═══════════════════════════════════════════════════════════════════════
# Generic cache helpers
# ═══════════════════════════════════════════════════════════════════════


async def cache_get(
    key: str, *, redis_client: aioredis.Redis | None = None
) -> str | None:
    """Return the cached string at ``key`` or ``None`` if missing."""
    client = redis_client or get_redis()
    return await client.get(_cache_key(key))


async def cache_set(
    key: str,
    value: str,
    ttl_seconds: int,
    *,
    redis_client: aioredis.Redis | None = None,
) -> None:
    """Store ``value`` under ``key`` with a TTL. Zero TTL is rejected — we
    never want a non-expiring cache entry by accident."""
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive — non-expiring cache forbidden.")
    client = redis_client or get_redis()
    await client.set(_cache_key(key), value, ex=ttl_seconds)


async def cache_delete(
    key: str, *, redis_client: aioredis.Redis | None = None
) -> bool:
    """Remove ``key``. Returns ``True`` if something was deleted."""
    client = redis_client or get_redis()
    return bool(await client.delete(_cache_key(key)))


async def cache_get_json(
    key: str, *, redis_client: aioredis.Redis | None = None
) -> Any | None:
    """JSON-decode the cached value; returns ``None`` on miss.

    Corrupt payloads log a warning and yield ``None`` — a poisoned cache
    entry should never 500 the webhook.
    """
    raw = await cache_get(key, redis_client=redis_client)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("cache.corrupt_json", key=key)
        return None


async def cache_set_json(
    key: str,
    value: Any,
    ttl_seconds: int,
    *,
    redis_client: aioredis.Redis | None = None,
) -> None:
    """JSON-encode and cache ``value``."""
    await cache_set(
        key,
        json.dumps(value, default=str),
        ttl_seconds,
        redis_client=redis_client,
    )


# ═══════════════════════════════════════════════════════════════════════
# Rate limiting (fixed-window counter)
# ═══════════════════════════════════════════════════════════════════════


async def rate_limit_check(
    key: str,
    max_requests: int,
    window_seconds: int,
    *,
    redis_client: aioredis.Redis | None = None,
) -> bool:
    """Fixed-window rate limiter — returns ``True`` if the call is allowed.

    Pipeline does INCR + EXPIRE in a single round-trip. EXPIRE is only
    meaningful on the first hit (returns 1) but issuing it unconditionally
    is harmless and saves a branch. The caller treats ``False`` as a 429.

    Args:
        key: Caller-supplied identity. Namespaced internally under
            ``rate:`` so webhook limits cannot collide with login limits.
        max_requests: Cap within the window.
        window_seconds: Window size; counter resets when the key expires.
    """
    if max_requests <= 0:
        raise ValueError("max_requests must be positive.")
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive.")

    client = redis_client or get_redis()
    pipe = client.pipeline(transaction=False)
    full_key = _rate_key(key)
    pipe.incr(full_key)
    pipe.expire(full_key, window_seconds)
    count, _ = await pipe.execute()
    return int(count) <= max_requests


async def rate_limit_reset(
    key: str, *, redis_client: aioredis.Redis | None = None
) -> None:
    """Drop the counter — useful for tests and admin tooling."""
    client = redis_client or get_redis()
    await client.delete(_rate_key(key))


# ═══════════════════════════════════════════════════════════════════════
# Kill switch
# ═══════════════════════════════════════════════════════════════════════


async def get_kill_switch_status(
    user_id: UUID | str, *, redis_client: aioredis.Redis | None = None
) -> str:
    """Return ``ACTIVE`` (default) or ``TRIPPED``.

    Default-to-ACTIVE means: if Redis is cold or the key is missing, we
    allow trades to proceed. The kill switch TRIPPED flag is always
    explicit — a failure mode where we forget to set it is safer than a
    failure mode where we can't honour an expired cache.
    """
    client = redis_client or get_redis()
    raw = await client.get(_kill_key(user_id))
    return raw if raw in (KILL_SWITCH_ACTIVE, KILL_SWITCH_TRIPPED) else KILL_SWITCH_ACTIVE


async def set_kill_switch_status(
    user_id: UUID | str,
    status: str,
    *,
    redis_client: aioredis.Redis | None = None,
) -> None:
    """Persist the kill-switch state — TRIPPED flags never expire."""
    if status not in (KILL_SWITCH_ACTIVE, KILL_SWITCH_TRIPPED):
        raise ValueError(
            f"kill-switch status must be {KILL_SWITCH_ACTIVE} or "
            f"{KILL_SWITCH_TRIPPED}, got {status!r}."
        )
    client = redis_client or get_redis()
    await client.set(_kill_key(user_id), status)


async def clear_kill_switch(
    user_id: UUID | str, *, redis_client: aioredis.Redis | None = None
) -> None:
    """Remove the kill-switch flag entirely (manual admin reset)."""
    client = redis_client or get_redis()
    await client.delete(_kill_key(user_id))


# ═══════════════════════════════════════════════════════════════════════
# Daily P&L
# ═══════════════════════════════════════════════════════════════════════


async def get_daily_pnl(
    user_id: UUID | str, *, redis_client: aioredis.Redis | None = None
) -> Decimal:
    """Return running P&L (Decimal) for the user's current trading day.

    Missing key returns ``Decimal("0")`` — the day hasn't recorded a
    trade yet. Corrupt numerics log and also return zero.
    """
    client = redis_client or get_redis()
    raw = await client.get(_pnl_key(user_id))
    if raw is None:
        return Decimal("0")
    try:
        return Decimal(raw)
    except (ValueError, ArithmeticError):
        logger.warning("pnl.corrupt_value", user_id=str(user_id), raw=raw)
        return Decimal("0")


async def set_daily_pnl(
    user_id: UUID | str,
    value: Decimal,
    *,
    ttl_seconds: int = 86400,
    redis_client: aioredis.Redis | None = None,
) -> None:
    """Write the day's P&L; default TTL ~24h so stale values auto-expire."""
    client = redis_client or get_redis()
    await client.set(_pnl_key(user_id), str(value), ex=ttl_seconds)


async def increment_daily_pnl(
    user_id: UUID | str,
    delta: Decimal,
    *,
    ttl_seconds: int = 86400,
    redis_client: aioredis.Redis | None = None,
) -> Decimal:
    """Atomically add ``delta`` to the user's daily P&L and return the new total.

    Uses GET+SET in a pipeline — not INCRBYFLOAT — because Decimal math
    on the broker-reported P&L must not lose precision to float rounding.
    """
    client = redis_client or get_redis()
    current = await get_daily_pnl(user_id, redis_client=client)
    new_total = current + delta
    await set_daily_pnl(
        user_id, new_total, ttl_seconds=ttl_seconds, redis_client=client
    )
    return new_total


# ═══════════════════════════════════════════════════════════════════════
# Positions cache
# ═══════════════════════════════════════════════════════════════════════


async def set_positions_cache(
    user_id: UUID | str,
    positions: Iterable[dict[str, Any]],
    *,
    ttl_seconds: int = 300,
    redis_client: aioredis.Redis | None = None,
) -> None:
    """Store the user's position snapshot as JSON.

    Short TTL (5 min by default) — positions are authoritative on the
    broker, we're only caching for fast reads from the kill switch.
    """
    client = redis_client or get_redis()
    payload = json.dumps(list(positions), default=str)
    await client.set(_pos_key(user_id), payload, ex=ttl_seconds)


async def get_positions_cache(
    user_id: UUID | str, *, redis_client: aioredis.Redis | None = None
) -> list[dict[str, Any]]:
    """Return the cached positions list (empty list on miss / corruption)."""
    client = redis_client or get_redis()
    raw = await client.get(_pos_key(user_id))
    if raw is None:
        return []
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("positions.corrupt_json", user_id=str(user_id))
        return []
    return decoded if isinstance(decoded, list) else []


# ═══════════════════════════════════════════════════════════════════════
# Idempotency
# ═══════════════════════════════════════════════════════════════════════


async def get_idempotency_key(
    signal_hash: str, *, redis_client: aioredis.Redis | None = None
) -> bool:
    """Return ``True`` if this ``signal_hash`` was already seen."""
    client = redis_client or get_redis()
    return await client.exists(_idem_key(signal_hash)) > 0


async def set_idempotency_key(
    signal_hash: str,
    *,
    ttl_seconds: int = 60,
    redis_client: aioredis.Redis | None = None,
) -> bool:
    """Claim the idempotency slot atomically.

    Returns ``True`` if we were the first caller (safe to proceed), or
    ``False`` if a duplicate request had already claimed it. Uses ``SET NX``
    so two concurrent requests cannot both see "first" — the race loser
    reads ``False`` and the caller returns 409.
    """
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive.")
    client = redis_client or get_redis()
    # ``nx=True`` → only set if not exists. Returns True on success, None on conflict.
    acquired = await client.set(
        _idem_key(signal_hash), "1", ex=ttl_seconds, nx=True
    )
    return bool(acquired)


__all__ = [
    "KILL_SWITCH_ACTIVE",
    "KILL_SWITCH_TRIPPED",
    "cache_delete",
    "cache_get",
    "cache_get_json",
    "cache_set",
    "cache_set_json",
    "clear_kill_switch",
    "close_redis",
    "get_daily_pnl",
    "get_idempotency_key",
    "get_kill_switch_status",
    "get_positions_cache",
    "get_redis",
    "increment_daily_pnl",
    "rate_limit_check",
    "rate_limit_reset",
    "set_daily_pnl",
    "set_idempotency_key",
    "set_kill_switch_status",
    "set_positions_cache",
]
