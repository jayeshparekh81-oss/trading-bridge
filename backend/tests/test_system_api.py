"""Tests for the /api/system router.

Powers the dashboard PAPER-MODE banner — must remain unauthenticated and
return all three master safety toggles in one read.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import config as app_config
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


def _make_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr("app.db.session.get_engine", lambda: _FakeEngine())

    async def _noop() -> None:
        return None

    monkeypatch.setattr("app.db.session.dispose_engine", _noop)

    fake_redis = MagicMock()
    fake_redis.ping = AsyncMock(return_value=True)
    fake_redis.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)

    return create_app()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    app_config.get_settings.cache_clear()
    yield
    app_config.get_settings.cache_clear()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    with TestClient(_make_app(monkeypatch)) as c:
        yield c


#: Fields on the UNAUTHENTICATED /api/system/mode payload that are not
#: booleans. Every entry here has been reviewed as safe to serve to anyone.
#: Keep it short; the all-booleans shape is the guard.
_NON_BOOLEAN_PUBLIC_FIELDS = {"tracking_epoch"}


class TestSystemMode:
    def test_returns_the_toggles_and_the_tracking_epoch(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/system/mode")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {
            "paper_mode",
            "kill_switch_check_enabled",
            "circuit_breaker_enabled",
            # Added 2026-09-09. Published so the UI can say "Record 1 Sept
            # 2026 se" with the date coming FROM THE SERVER — a hardcoded
            # date in the frontend would be a second spelling that drifts
            # the day the epoch moves.
            "tracking_epoch",
        }
        for key, value in body.items():
            if key in _NON_BOOLEAN_PUBLIC_FIELDS:
                continue
            assert isinstance(value, bool), f"{key} should be a boolean"

    def test_reflects_paper_mode_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
        app_config.get_settings.cache_clear()
        with TestClient(_make_app(monkeypatch)) as c:
            assert c.get("/api/system/mode").json()["paper_mode"] is True

    def test_reflects_paper_mode_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        app_config.get_settings.cache_clear()
        with TestClient(_make_app(monkeypatch)) as c:
            assert c.get("/api/system/mode").json()["paper_mode"] is False

    def test_no_auth_required(self, client: TestClient) -> None:
        """The banner needs to render before/regardless of auth state.
        No Authorization header → still 200, never 401."""
        resp = client.get("/api/system/mode")
        assert resp.status_code == 200
        assert resp.status_code != 401

    def test_no_secrets_in_response(self, client: TestClient) -> None:
        """Belt-and-braces: this endpoint is UNAUTHENTICATED, so the shape
        itself is the safety property. Everything is a boolean toggle except
        an explicit, reviewed allowlist. No tokens, no URLs, no PII. A future
        edit that adds an unlisted non-boolean field breaks this loudly.

        The allowlist is deliberately narrow rather than removed: making the
        payload "any JSON" would delete the guard instead of narrowing it.
        ``tracking_epoch`` is on it because a cut-off DATE is public by
        design — it is printed to customers on the affected screens."""
        body = client.get("/api/system/mode").json()
        for key, value in body.items():
            if key in _NON_BOOLEAN_PUBLIC_FIELDS:
                # Still typed, still asserted — just not a boolean.
                assert value is None or isinstance(value, str), (
                    f"{key} is allowlisted as a public string/None, "
                    f"got {type(value).__name__}"
                )
                continue
            assert isinstance(value, bool), (
                f"Non-boolean field would risk leaking sensitive data; "
                f"got {key} of type {type(value).__name__}"
            )
