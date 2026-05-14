"""Fixtures for brokers/ tests (dhan_historical + dhan_websocket).

Provides:
    * ``fake_redis`` (autouse) — substitutes :func:`app.core.redis_client.get_redis`
      with a :class:`fakeredis.aioredis.FakeRedis` instance. Needed for
      the per-user rate-limit check in ``DhanHistoricalClient`` and for
      publish_json in the WS adapter.
    * ``user_id`` — a stable UUID string used as the per-user rate-limit
      key in dhan_historical tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import redis_client


@pytest_asyncio.fixture(autouse=True)
async def fake_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    """Process-wide async Redis substituted for fakeredis."""
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def user_id() -> str:
    """Stable per-test UUID — keeps the per-user rate-limit key predictable."""
    return str(UUID("11111111-1111-1111-1111-111111111111"))
