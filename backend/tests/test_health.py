"""Tests for the /health router.

Re-uses the DB + Redis mocking pattern from ``test_main.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


class _FakeConn:
    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        return MagicMock()

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None


class _FakeEngine:
    def connect(self) -> _FakeConn:
        return _FakeConn()

    async def dispose(self) -> None:
        return None


def _make_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    redis_ok: bool = True,
    db_ok: bool = True,
) -> FastAPI:
    if db_ok:
        engine = _FakeEngine()
    else:
        class _BrokenEngine:
            def connect(self) -> Any:
                raise RuntimeError("db down")

            async def dispose(self) -> None:  # pragma: no cover
                return None

        engine = _BrokenEngine()  # type: ignore[assignment]

    async def _noop() -> None:
        return None

    monkeypatch.setattr("app.db.session.get_engine", lambda: engine)
    monkeypatch.setattr("app.db.session.dispose_engine", _noop)

    fake_redis = MagicMock()
    if redis_ok:
        fake_redis.ping = AsyncMock(return_value=True)
    else:
        fake_redis.ping = AsyncMock(side_effect=RuntimeError("redis down"))
    fake_redis.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

    return create_app()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    with TestClient(_make_app(monkeypatch)) as c:
        yield c


class TestLiveness:
    def test_health_ok_without_io(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_slash_variant(self, client: TestClient) -> None:
        resp = client.get("/health/")
        assert resp.status_code == 200


class TestReadiness:
    def test_ready_when_both_up(self, client: TestClient) -> None:
        body = client.get("/health/ready").json()
        assert body == {"status": "ok", "db": True, "redis": True}

    def test_degraded_when_redis_down(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = _make_app(monkeypatch, redis_ok=False)
        with TestClient(app) as c:
            body = c.get("/health/ready").json()
        assert body["status"] == "degraded"
        assert body["redis"] is False

    def test_degraded_when_db_down(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = _make_app(monkeypatch, db_ok=False)
        with TestClient(app) as c:
            body = c.get("/health/ready").json()
        assert body["status"] == "degraded"
        assert body["db"] is False


class TestDetailed:
    def test_detailed_reports_latency(self, client: TestClient) -> None:
        body = client.get("/health/detailed").json()
        assert body["status"] == "ok"
        assert body["db"]["ok"] is True
        assert body["redis"]["ok"] is True
        assert isinstance(body["db"]["latency_ms"], (int, float))
        assert isinstance(body["redis"]["latency_ms"], (int, float))

    def test_detailed_handles_redis_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = _make_app(monkeypatch, redis_ok=False)
        with TestClient(app) as c:
            body = c.get("/health/detailed").json()
        assert body["redis"]["ok"] is False
        assert body["redis"]["latency_ms"] is None
