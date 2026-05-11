"""Fixtures for services/ tests (chart_redis pub/sub helpers).

Provides:
    * ``fake_redis`` (autouse) — substitutes :func:`app.core.redis_client.get_redis`
      with a :class:`fakeredis.aioredis.FakeRedis` instance.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import redis_client


@pytest_asyncio.fixture(autouse=True)
async def fake_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    """Process-wide async Redis substituted for fakeredis.

    ``autouse=True`` so every test in this subdir gets the substitute
    without having to list it as an argument.
    """
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()
