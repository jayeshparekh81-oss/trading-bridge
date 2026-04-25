"""Daily message rate limiter for AlgoMitra AI calls.

Per-user, midnight-IST reset. Backed by Redis so it survives backend
restarts and works across multiple workers. Returns a structured tuple
so the API layer can surface remaining quota in its response.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.redis_client import get_redis


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of one ``check_and_increment`` call."""

    allowed: bool
    used: int
    limit: int
    reset_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def _seconds_until_ist_midnight(now: datetime) -> tuple[int, datetime]:
    """Return ``(seconds_to_reset, reset_at_utc)``.

    The "day" boundary is IST midnight (UTC+5:30). At 23:59 IST, a
    successful request gets ~1 minute of TTL, then the counter resets
    cleanly.
    """
    # Convert "now" to a tz-aware UTC datetime, then offset to IST.
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    ist_offset = timedelta(hours=5, minutes=30)
    ist_now = now + ist_offset
    ist_midnight = (ist_now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    reset_at_utc = ist_midnight - ist_offset
    seconds = int((reset_at_utc - now).total_seconds())
    return max(seconds, 60), reset_at_utc


async def check_and_increment(
    user_id: UUID | str,
    *,
    daily_limit: int,
) -> RateLimitResult:
    """Increment the day's counter atomically and report whether the call is allowed.

    ``allowed=False`` means the user is over quota — caller should 429
    without burning a Claude API call.
    """
    if daily_limit <= 0:
        raise ValueError("daily_limit must be positive")

    client = get_redis()
    key = f"rate:algomitra:{user_id}"
    ttl, reset_at = _seconds_until_ist_midnight(datetime.now(UTC))

    pipe = client.pipeline(transaction=False)
    pipe.incr(key)
    pipe.expire(key, ttl, nx=True)  # set TTL only if not already set
    used_raw, _ = await pipe.execute()
    used = int(used_raw)

    return RateLimitResult(
        allowed=used <= daily_limit,
        used=used,
        limit=daily_limit,
        reset_at=reset_at,
    )


async def peek(user_id: UUID | str, *, daily_limit: int) -> RateLimitResult:
    """Read the current counter without incrementing — useful for `GET /quota`."""
    client = get_redis()
    raw = await client.get(f"rate:algomitra:{user_id}")
    used = int(raw) if raw is not None else 0
    _, reset_at = _seconds_until_ist_midnight(datetime.now(UTC))
    return RateLimitResult(
        allowed=used < daily_limit,
        used=used,
        limit=daily_limit,
        reset_at=reset_at,
    )


__all__ = ["RateLimitResult", "check_and_increment", "peek"]
