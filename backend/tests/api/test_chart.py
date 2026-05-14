"""Tests for :mod:`app.api.chart` — REST + WebSocket routes.

Coverage strategy:
    * REST routes go through :class:`fastapi.testclient.TestClient`
      with the auth dependency overridden to a synthetic ``User``.
    * DB access is faked via an AsyncMock that returns a scripted
      ``BrokerCredential`` row, installed as a FastAPI dependency override.
    * ``decrypt_credential`` is monkeypatched to identity so the
      encrypted-column round-trip costs nothing.
    * :class:`DhanBroker` and :class:`DhanHistoricalClient` are
      monkeypatched at their import sites in ``app.api.chart``.
    * Redis (cache + pub/sub) is fakeredis via the autouse fixture.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fake_aioredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import chart as chart_mod
from app.api.chart import _envelope_for, _history_cache_key
from app.brokers.dhan_historical import (
    BrokerAuthError,
    BrokerInvalidParamsError,
    BrokerRateLimitError,
    BrokerUpstreamError,
)
from app.db.session import get_session
from app.schemas.candle import ChartEventType, Timeframe
from app.services import chart_redis
from tests._chart_helpers import make_candle, utc_datetime


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _default_creds_row() -> MagicMock:
    row = MagicMock()
    row.client_id_enc = "client-id-plain"
    row.api_key_enc = "api-key-plain"
    row.api_secret_enc = "api-secret-plain"
    row.access_token_enc = "access-token-plain"
    row.refresh_token_enc = "refresh-token-plain"
    row.token_expires_at = utc_datetime()
    return row


def _patch_chart_deps(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    *,
    security_id: str | Exception = "13",
    candles_or_exc: list | Exception | None = None,
    db_returns_row: bool = True,
    creds_row: MagicMock | None = None,
) -> None:
    """One-stop monkeypatch for the chart-route dependency stack."""
    monkeypatch.setattr(chart_mod, "decrypt_credential", lambda v: v)

    class _StubBroker:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def get_security_id(self, *_args: Any, **_kwargs: Any) -> str:
            if isinstance(security_id, Exception):
                raise security_id
            return security_id

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(chart_mod, "DhanBroker", _StubBroker)

    class _StubHistorical:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _StubHistorical:
            return self

        async def __aexit__(self, *_exc: Any) -> None:
            pass

        async def get_historical_ohlc(self, **_kwargs: Any) -> list:
            if isinstance(candles_or_exc, Exception):
                raise candles_or_exc
            return list(candles_or_exc) if candles_or_exc is not None else []

    monkeypatch.setattr(chart_mod, "DhanHistoricalClient", _StubHistorical)

    row = (
        creds_row
        if creds_row is not None
        else (_default_creds_row() if db_returns_row else None)
    )

    async def get_fake_session() -> Any:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=row)
        session.execute = AsyncMock(return_value=result)
        yield session

    client.app.dependency_overrides[get_session] = get_fake_session


@pytest.fixture
def patched_client(chart_app: FastAPI) -> TestClient:
    """TestClient whose chart_app is ready for dependency_overrides
    installed by ``_patch_chart_deps`` inside each test."""
    return TestClient(chart_app)


# ═══════════════════════════════════════════════════════════════════════
# GET /api/chart/history
# ═══════════════════════════════════════════════════════════════════════


class TestGetChartHistory:
    def _params(self, **overrides: Any) -> dict[str, str]:
        base = {
            "symbol": "NIFTY",
            "exchange": "NSE",
            "timeframe": "5m",
            "from": "2026-05-11T09:15:00+05:30",
            "to": "2026-05-11T15:30:00+05:30",
        }
        base.update(overrides)
        return base

    def test_happy_path_returns_candles(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch,
            patched_client,
            candles_or_exc=[make_candle(timeframe=Timeframe.FIVE_MIN)],
        )
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "NIFTY"
        assert body["timeframe"] == "5m"
        assert body["cached"] is False
        assert len(body["candles"]) == 1

    def test_cache_hit_returns_cached_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch, patched_client, candles_or_exc=[make_candle()]
        )
        first = patched_client.get("/api/chart/history", params=self._params())
        assert first.status_code == 200
        assert first.json()["cached"] is False
        second = patched_client.get("/api/chart/history", params=self._params())
        assert second.status_code == 200
        assert second.json()["cached"] is True

    def test_corrupted_cache_falls_through_to_fresh_fetch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        _patch_chart_deps(
            monkeypatch, patched_client, candles_or_exc=[make_candle()]
        )
        params = self._params()
        from_ts = datetime.fromisoformat(params["from"])
        to_ts = datetime.fromisoformat(params["to"])
        key = _history_cache_key("NIFTY", Timeframe.FIVE_MIN, from_ts, to_ts)
        from app.core.redis_client import cache_set

        async def _seed() -> None:
            await cache_set(key, "{not valid json}", ttl_seconds=60)

        asyncio.new_event_loop().run_until_complete(_seed())

        resp = patched_client.get("/api/chart/history", params=params)
        assert resp.status_code == 200
        assert resp.json()["cached"] is False

    def test_naive_from_returns_400(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(monkeypatch, patched_client, candles_or_exc=[])
        resp = patched_client.get(
            "/api/chart/history",
            params=self._params(**{"from": "2026-05-11T09:15:00"}),
        )
        assert resp.status_code == 400
        assert "timezone" in resp.json()["detail"].lower()

    def test_no_dhan_link_returns_412(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(monkeypatch, patched_client, db_returns_row=False)
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 412
        assert "Dhan broker link" in resp.json()["detail"]

    def test_missing_access_token_returns_412(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        row = _default_creds_row()
        row.access_token_enc = None
        _patch_chart_deps(monkeypatch, patched_client, creds_row=row)
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 412
        assert "access token" in resp.json()["detail"].lower()

    def test_symbol_not_in_scrip_master_returns_404(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch,
            patched_client,
            security_id=Exception("scrip lookup failed"),
        )
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 404
        assert "scrip master" in resp.json()["detail"].lower()

    def test_broker_auth_error_returns_401(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch,
            patched_client,
            candles_or_exc=BrokerAuthError("token expired"),
        )
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 401
        assert "token expired" in resp.json()["detail"]

    def test_broker_invalid_params_returns_400(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch,
            patched_client,
            candles_or_exc=BrokerInvalidParamsError("range too wide"),
        )
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 400
        assert "range too wide" in resp.json()["detail"]

    def test_broker_rate_limit_returns_429(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch,
            patched_client,
            candles_or_exc=BrokerRateLimitError("5/sec exhausted"),
        )
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 429
        assert "5/sec" in resp.json()["detail"]

    def test_broker_upstream_returns_502(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch,
            patched_client,
            candles_or_exc=BrokerUpstreamError("array mismatch"),
        )
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 502
        assert "array mismatch" in resp.json()["detail"]

    def test_unsupported_exchange_returns_400(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        _patch_chart_deps(monkeypatch, patched_client, candles_or_exc=[])
        monkeypatch.setattr(chart_mod, "_EXCHANGE_TO_SEGMENT", {})
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 400
        assert "supported nahi" in resp.json()["detail"]

    def test_cache_set_failure_does_not_fail_request(
        self,
        monkeypatch: pytest.MonkeyPatch,
        patched_client: TestClient,
    ) -> None:
        _patch_chart_deps(
            monkeypatch, patched_client, candles_or_exc=[make_candle()]
        )

        async def _failing_cache_set(*_args: Any, **_kwargs: Any) -> None:
            raise ConnectionError("redis down")

        monkeypatch.setattr(chart_mod, "cache_set", _failing_cache_set)
        resp = patched_client.get("/api/chart/history", params=self._params())
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# GET /api/chart/ws-token
# ═══════════════════════════════════════════════════════════════════════


class TestGetWsToken:
    def test_issues_15_min_token(self, patched_client: TestClient) -> None:
        resp = patched_client.get("/api/chart/ws-token")
        assert resp.status_code == 200
        body = resp.json()
        assert body["expires_in"] == 900
        assert isinstance(body["token"], str)
        assert len(body["token"]) > 20  # JWT is not tiny


# ═══════════════════════════════════════════════════════════════════════
# WebSocket /ws/chart/{symbol}/{timeframe}
# ═══════════════════════════════════════════════════════════════════════


class TestChartWebSocket:
    def _mint_token(self, client: TestClient) -> str:
        resp = client.get("/api/chart/ws-token")
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_missing_token_closes_4401(
        self, patched_client: TestClient
    ) -> None:
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with patched_client.websocket_connect("/ws/chart/NIFTY/5m"):
                pass
        assert excinfo.value.code == 4401

    def test_invalid_token_closes_4401(
        self, patched_client: TestClient
    ) -> None:
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with patched_client.websocket_connect(
                "/ws/chart/NIFTY/5m?token=not-a-jwt"
            ):
                pass
        assert excinfo.value.code == 4401

    def test_bad_timeframe_closes_4400(
        self, patched_client: TestClient
    ) -> None:
        token = self._mint_token(patched_client)
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with patched_client.websocket_connect(
                f"/ws/chart/NIFTY/4m?token={token}"
            ):
                pass
        assert excinfo.value.code == 4400

    def test_bad_symbol_closes_4400(
        self, patched_client: TestClient
    ) -> None:
        token = self._mint_token(patched_client)
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with patched_client.websocket_connect(
                f"/ws/chart/NIFTY.NS/5m?token={token}"
            ):
                pass
        assert excinfo.value.code == 4400

    def test_happy_path_receives_candle_envelope(
        self,
        patched_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Open WS, publish a candle, receive the envelope."""
        # Lower the poll timeout so the test doesn't wait the default 1s
        # between read attempts when the publish lands fast.
        monkeypatch.setattr(chart_mod, "_WS_POLL_TIMEOUT_S", 0.05)
        token = self._mint_token(patched_client)
        candle = make_candle(timeframe=Timeframe.FIVE_MIN)
        with patched_client.websocket_connect(
            f"/ws/chart/NIFTY/5m?token={token}"
        ) as ws:
            async def _pub() -> None:
                # Tiny grace period so the handler has reached its read
                # loop before we publish (otherwise fakeredis drops the
                # message).
                await asyncio.sleep(0.1)
                await chart_redis.publish_json(
                    chart_redis.chart_candles_channel("NIFTY", "5m"),
                    candle.model_dump(mode="json"),
                )

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_pub())
            finally:
                loop.close()

            # Drain until we see the candle event (may be preceded by a
            # heartbeat if scheduling is slow).
            for _ in range(20):
                frame = ws.receive_json()
                if frame.get("event") == "candle":
                    assert frame["data"]["symbol"] == "NIFTY"
                    return
            pytest.fail("Did not receive candle envelope within drain budget")

    def test_heartbeat_emitted_after_silence(
        self,
        patched_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Silent channel → heartbeat frame after the interval elapses."""
        # Make the heartbeat fire on the first idle poll.
        monkeypatch.setattr(chart_mod, "_WS_HEARTBEAT_INTERVAL_S", 0.01)
        monkeypatch.setattr(chart_mod, "_WS_POLL_TIMEOUT_S", 0.05)
        token = self._mint_token(patched_client)
        with patched_client.websocket_connect(
            f"/ws/chart/NIFTY/5m?token={token}"
        ) as ws:
            frame = ws.receive_json()
            assert frame["event"] == ChartEventType.HEARTBEAT.value
            assert "at" in frame

    def test_unexpected_error_closes_1011(
        self,
        patched_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An exception inside the read loop closes the WS with 1011."""
        monkeypatch.setattr(chart_mod, "_WS_POLL_TIMEOUT_S", 0.05)

        # _envelope_for raises → triggers ``except Exception`` arm.
        def boom(_msg: Any) -> dict[str, Any]:
            raise RuntimeError("envelope boom")

        monkeypatch.setattr(chart_mod, "_envelope_for", boom)
        token = self._mint_token(patched_client)
        from starlette.websockets import WebSocketDisconnect
        with patched_client.websocket_connect(
            f"/ws/chart/NIFTY/5m?token={token}"
        ) as ws:
            async def _pub() -> None:
                await asyncio.sleep(0.05)
                await chart_redis.publish_json(
                    chart_redis.chart_candles_channel("NIFTY", "5m"),
                    {"x": 1},
                )

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_pub())
            finally:
                loop.close()

            with pytest.raises(WebSocketDisconnect) as excinfo:
                # Read should fail because the server closed with 1011.
                while True:
                    ws.receive_json()
            assert excinfo.value.code == 1011

    def test_cleanup_exception_swallowed(
        self,
        patched_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """pubsub.unsubscribe + pubsub.aclose failures don't bubble."""
        monkeypatch.setattr(chart_mod, "_WS_POLL_TIMEOUT_S", 0.05)
        monkeypatch.setattr(chart_mod, "_WS_HEARTBEAT_INTERVAL_S", 100.0)

        real_subscribe = chart_redis.subscribe

        async def _subscribe_with_bad_cleanup(*args: Any, **kwargs: Any) -> Any:
            pubsub = await real_subscribe(*args, **kwargs)

            async def _bad_unsubscribe(*_a: Any, **_kw: Any) -> None:
                raise RuntimeError("unsubscribe boom")

            async def _bad_aclose() -> None:
                raise RuntimeError("aclose boom")

            pubsub.unsubscribe = _bad_unsubscribe  # type: ignore[method-assign]
            pubsub.aclose = _bad_aclose  # type: ignore[method-assign]
            return pubsub

        monkeypatch.setattr(chart_mod, "subscribe", _subscribe_with_bad_cleanup)

        token = self._mint_token(patched_client)
        with patched_client.websocket_connect(
            f"/ws/chart/NIFTY/5m?token={token}"
        ):
            pass  # Immediately close — cleanup failure must not propagate.

    def test_malformed_payload_skipped(
        self,
        patched_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A bad JSON payload on the channel must NOT crash the handler."""
        monkeypatch.setattr(chart_mod, "_WS_POLL_TIMEOUT_S", 0.05)
        monkeypatch.setattr(chart_mod, "_WS_HEARTBEAT_INTERVAL_S", 0.01)
        token = self._mint_token(patched_client)
        with patched_client.websocket_connect(
            f"/ws/chart/NIFTY/5m?token={token}"
        ) as ws:
            async def _bad_pub() -> None:
                await asyncio.sleep(0.05)
                from app.core.redis_client import get_redis
                client = get_redis()
                await client.publish(
                    chart_redis.chart_candles_channel("NIFTY", "5m"),
                    "{not json",
                )

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_bad_pub())
            finally:
                loop.close()

            # The handler should still emit at least one heartbeat —
            # never a "candle" frame from the bad publish.
            frame = ws.receive_json()
            assert frame["event"] in {
                ChartEventType.HEARTBEAT.value,
                ChartEventType.CANDLE.value,
            }
            # Specifically confirm we did NOT get a candle envelope.
            if frame["event"] == ChartEventType.CANDLE.value:
                pytest.fail("Bad payload leaked to client as candle")


# ═══════════════════════════════════════════════════════════════════════
# _envelope_for unit tests
# ═══════════════════════════════════════════════════════════════════════


class TestEnvelopeFor:
    def test_control_event_passes_through(self) -> None:
        msg = {
            "channel": "chart:control:NIFTY",
            "data": json.dumps(
                {"event": "broker_disconnected", "symbol": "NIFTY"}
            ),
        }
        env = _envelope_for(msg)
        assert env == {"event": "broker_disconnected", "symbol": "NIFTY"}

    def test_candle_payload_wrapped(self) -> None:
        msg = {
            "channel": "chart:candles:NIFTY:5m",
            "data": json.dumps({"symbol": "NIFTY", "close": "100.0"}),
        }
        env = _envelope_for(msg)
        assert env is not None
        assert env["event"] == ChartEventType.CANDLE.value
        assert env["data"] == {"symbol": "NIFTY", "close": "100.0"}

    def test_bytes_data_decoded(self) -> None:
        msg = {
            "channel": "chart:candles:NIFTY:5m",
            "data": b'{"symbol": "NIFTY"}',
        }
        env = _envelope_for(msg)
        assert env is not None
        assert env["data"]["symbol"] == "NIFTY"

    def test_bad_utf8_bytes_returns_none(self) -> None:
        msg = {
            "channel": "chart:candles:NIFTY:5m",
            "data": b"\xff\xfe\xfd",
        }
        assert _envelope_for(msg) is None

    def test_non_str_non_bytes_data_returns_none(self) -> None:
        msg = {"channel": "x", "data": 12345}
        assert _envelope_for(msg) is None

    def test_malformed_json_returns_none(self) -> None:
        msg = {"channel": "x", "data": "{not json}"}
        assert _envelope_for(msg) is None


# ═══════════════════════════════════════════════════════════════════════
# _resolve_security_id direct
# ═══════════════════════════════════════════════════════════════════════


class TestResolveSecurityId:
    @pytest.mark.asyncio
    async def test_propagates_security_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _StubBroker:
            def __init__(self, *_a: Any, **_kw: Any) -> None:
                pass

            async def get_security_id(self, *_a: Any, **_kw: Any) -> str:
                return "11536"

            async def aclose(self) -> None:
                pass

        monkeypatch.setattr(chart_mod, "DhanBroker", _StubBroker)
        from app.schemas.broker import (
            BrokerCredentials,
            BrokerName,
            Exchange,
        )

        creds = BrokerCredentials(
            broker=BrokerName.DHAN,
            user_id="u",
            client_id="C",
            api_key="K",
            api_secret="S",
            access_token="T",
        )
        result = await chart_mod._resolve_security_id(creds, "NIFTY", Exchange.NSE)
        assert result == "11536"
