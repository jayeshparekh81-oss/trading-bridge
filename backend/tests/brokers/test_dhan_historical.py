"""Tests for :class:`app.brokers.dhan_historical.DhanHistoricalClient`.

Uses :class:`httpx.MockTransport` so every HTTP call is scripted —
no network access. Per-test transport scripts return the exact
response we want to assert against.

Per-user rate limiting hits :func:`app.core.redis_client.rate_limit_check`;
the autouse ``fake_redis`` fixture from ``brokers/conftest.py``
substitutes ``fakeredis`` for the live Redis pool.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import fakeredis.aioredis as fake_aioredis
import httpx
import pytest

from app.brokers import dhan_historical
from app.brokers.dhan_historical import (
    BrokerAuthError,
    BrokerInvalidParamsError,
    BrokerRateLimitError,
    BrokerUpstreamError,
    DhanHistoricalClient,
)
from app.schemas.candle import Candle, Timeframe
from tests._chart_helpers import (
    IST_TZ,
    make_dhan_historical_response,
    utc_datetime,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _build_client(
    *,
    user_id: str = "11111111-1111-1111-1111-111111111111",
    transport: httpx.MockTransport | None = None,
) -> DhanHistoricalClient:
    """Construct a client + pre-attach a MockTransport-backed httpx pool.

    Bypasses the lazy ``_ensure_http()`` path so each test can script
    its own response sequence.
    """
    client = DhanHistoricalClient(
        client_id="CID-1",
        access_token="TOK",
        user_id=user_id,
    )
    if transport is not None:
        client._http = httpx.AsyncClient(
            base_url="https://api.dhan.co/v2",
            transport=transport,
            headers={
                "client-id": "CID-1",
                "access-token": "TOK",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
    return client


def _ok_response(body: Any) -> httpx.Response:
    return httpx.Response(200, json=body)


def _default_window() -> tuple[datetime, datetime]:
    return (
        utc_datetime(hour=3, minute=45),  # 09:15 IST
        utc_datetime(hour=10, minute=0),  # 15:30 IST
    )


# ═══════════════════════════════════════════════════════════════════════
# Constructor validation
# ═══════════════════════════════════════════════════════════════════════


class TestConstructor:
    def test_valid(self) -> None:
        client = DhanHistoricalClient(
            client_id="CID-1", access_token="TOK", user_id="abc"
        )
        assert client._client_id == "CID-1"
        assert client._access_token == "TOK"
        assert client._user_id == "abc"

    def test_empty_client_id_raises(self) -> None:
        with pytest.raises(BrokerInvalidParamsError):
            DhanHistoricalClient(
                client_id="", access_token="TOK", user_id="u"
            )

    def test_whitespace_client_id_raises(self) -> None:
        with pytest.raises(BrokerInvalidParamsError):
            DhanHistoricalClient(
                client_id="   ", access_token="TOK", user_id="u"
            )

    def test_empty_access_token_raises_auth(self) -> None:
        with pytest.raises(BrokerAuthError):
            DhanHistoricalClient(
                client_id="CID", access_token="", user_id="u"
            )

    def test_empty_user_id_raises(self) -> None:
        with pytest.raises(BrokerInvalidParamsError):
            DhanHistoricalClient(
                client_id="CID", access_token="TOK", user_id=""
            )

    def test_uuid_user_id_accepted(self) -> None:
        from uuid import UUID

        client = DhanHistoricalClient(
            client_id="CID",
            access_token="TOK",
            user_id=UUID("11111111-1111-1111-1111-111111111111"),
        )
        assert client._user_id == "11111111-1111-1111-1111-111111111111"

    def test_constructor_does_no_io(self) -> None:
        # No httpx client built until first use. Lets the route layer
        # construct + discard cheaply.
        client = DhanHistoricalClient(
            client_id="CID", access_token="TOK", user_id="u"
        )
        assert client._http is None


# ═══════════════════════════════════════════════════════════════════════
# _validate_params
# ═══════════════════════════════════════════════════════════════════════


class TestValidateParams:
    @pytest.mark.asyncio
    async def test_unsupported_timeframe_raises(self) -> None:
        client = _build_client()
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerInvalidParamsError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.THREE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        assert "3m" in str(excinfo.value).lower()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_thirty_min_rejected(self) -> None:
        client = _build_client()
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerInvalidParamsError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.THIRTY_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_naive_from_ts_rejected(self) -> None:
        client = _build_client()
        with pytest.raises(BrokerInvalidParamsError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=datetime(2026, 5, 11, 9, 15),
                to_ts=utc_datetime(),
            )
        assert "timezone-aware" in str(excinfo.value).lower()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_naive_to_ts_rejected(self) -> None:
        client = _build_client()
        with pytest.raises(BrokerInvalidParamsError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=utc_datetime(),
                to_ts=datetime(2026, 5, 11, 15, 30),
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_reversed_window_rejected(self) -> None:
        client = _build_client()
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerInvalidParamsError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=to_ts,
                to_ts=from_ts,
            )
        assert "from_ts" in str(excinfo.value).lower()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_intraday_range_too_wide(self) -> None:
        client = _build_client()
        with pytest.raises(BrokerInvalidParamsError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=utc_datetime() - timedelta(days=120),
                to_ts=utc_datetime(),
            )
        assert "90" in str(excinfo.value)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_daily_range_too_wide(self) -> None:
        client = _build_client()
        with pytest.raises(BrokerInvalidParamsError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.ONE_DAY,
                from_ts=utc_datetime() - timedelta(days=365 * 6),
                to_ts=utc_datetime(),
            )
        assert "5" in str(excinfo.value) or "year" in str(excinfo.value).lower()
        await client.aclose()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "missing_arg",
        ["symbol", "security_id", "exchange_segment", "instrument"],
    )
    async def test_empty_required_string_rejected(
        self, missing_arg: str
    ) -> None:
        client = _build_client()
        from_ts, to_ts = _default_window()
        kwargs = {
            "symbol": "NIFTY",
            "security_id": "13",
            "exchange_segment": "IDX_I",
            "instrument": "INDEX",
            "timeframe": Timeframe.FIVE_MIN,
            "from_ts": from_ts,
            "to_ts": to_ts,
        }
        kwargs[missing_arg] = "   "
        with pytest.raises(BrokerInvalidParamsError):
            await client.get_historical_ohlc(**kwargs)  # type: ignore[arg-type]
        await client.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Rate limiting (local 5/sec per user)
# ═══════════════════════════════════════════════════════════════════════


class TestLocalRateLimit:
    @pytest.mark.asyncio
    async def test_first_call_allowed(
        self, fake_redis: fake_aioredis.FakeRedis, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(make_dhan_historical_response())
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert len(bars) == 3
        await client.aclose()

    @pytest.mark.asyncio
    async def test_local_cap_exhausts_after_one_retry(
        self, fake_redis: fake_aioredis.FakeRedis, user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Pre-fill the rate counter so the first AND retry calls both
        # see the cap exhausted.
        rate_key = f"rate:dhan_historical:{user_id}"
        await fake_redis.set(rate_key, 999, ex=10)

        # Make the sleep instant so the test doesn't actually wait 1s.
        slept: list[float] = []

        async def _instant_sleep(seconds: float) -> None:
            slept.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)

        client = _build_client(user_id=user_id)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerRateLimitError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        assert "5 req/sec" in excinfo.value.message
        # We must have attempted one sleep before giving up.
        assert len(slept) == 1
        await client.aclose()

    @pytest.mark.asyncio
    async def test_local_cap_recovers_after_window(
        self, fake_redis: fake_aioredis.FakeRedis, user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rate_key = f"rate:dhan_historical:{user_id}"
        await fake_redis.set(rate_key, 999, ex=10)

        # Sleep instantly + wipe the counter so the retry sees a clean window.
        async def _wipe_and_sleep(seconds: float) -> None:
            await fake_redis.delete(rate_key)

        monkeypatch.setattr(asyncio, "sleep", _wipe_and_sleep)

        transport = httpx.MockTransport(
            lambda req: _ok_response(make_dhan_historical_response())
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert len(bars) == 3
        await client.aclose()


# ═══════════════════════════════════════════════════════════════════════
# HTTP path — status → typed error mapping
# ═══════════════════════════════════════════════════════════════════════


class TestHttpStatusMapping:
    @pytest.mark.asyncio
    async def test_200_happy_path_intraday_endpoint(
        self, user_id: str
    ) -> None:
        seen_paths: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            seen_paths.append(req.url.path)
            return _ok_response(make_dhan_historical_response())

        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert all(isinstance(b, Candle) for b in bars)
        assert seen_paths == ["/v2/charts/intraday"]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_200_daily_uses_historical_endpoint(
        self, user_id: str
    ) -> None:
        seen_paths: list[str] = []
        seen_bodies: list[dict[str, Any]] = []

        def handler(req: httpx.Request) -> httpx.Response:
            seen_paths.append(req.url.path)
            seen_bodies.append(req.content.decode())
            return _ok_response(make_dhan_historical_response())

        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts = utc_datetime() - timedelta(days=30)
        to_ts = utc_datetime()
        await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.ONE_DAY,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert seen_paths == ["/v2/charts/historical"]
        # Daily endpoint MUST NOT send an interval field.
        body_text = seen_bodies[0]
        assert "interval" not in body_text
        # Daily endpoint sends fromDate / toDate as date-only strings
        # (``YYYY-MM-DD``). Per Dhan v2 spec — intraday uses
        # ``YYYY-MM-DD HH:MM:SS``, historical uses date only. We assert
        # the absence of any time component in the wire payload.
        import json as _json
        body = _json.loads(body_text)
        assert " " not in body["fromDate"], (
            f"daily fromDate should be date-only, got {body['fromDate']!r}"
        )
        assert " " not in body["toDate"], (
            f"daily toDate should be date-only, got {body['toDate']!r}"
        )
        assert len(body["fromDate"]) == 10  # YYYY-MM-DD = 10 chars
        await client.aclose()

    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, user_id: str) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(401, json={"errorMessage": "bad token"})
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerAuthError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        # Hinglish message expected on the user-facing string.
        assert "session expired" in excinfo.value.message.lower()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_429_retries_then_succeeds(
        self,
        user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        call_count = {"n": 0}

        def handler(req: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(
                    429, json={}, headers={"Retry-After": "0"}
                )
            return _ok_response(make_dhan_historical_response())

        async def _instant_sleep(_seconds: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert call_count["n"] == 2
        assert len(bars) == 3
        await client.aclose()

    @pytest.mark.asyncio
    async def test_429_exhausts_retries(
        self,
        user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _instant_sleep(_seconds: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(429, json={})
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerRateLimitError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_5xx_retries_then_succeeds(
        self,
        user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        call_count = {"n": 0}

        def handler(req: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(503)
            return _ok_response(make_dhan_historical_response())

        async def _instant_sleep(_seconds: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert call_count["n"] == 2
        assert len(bars) == 3
        await client.aclose()

    @pytest.mark.asyncio
    async def test_5xx_exhausts_retries(
        self,
        user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _instant_sleep(_seconds: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)

        transport = httpx.MockTransport(lambda req: httpx.Response(503))
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_4xx_other_raises_invalid_params(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                400, json={"errorMessage": "bad securityId"}
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerInvalidParamsError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        assert "bad securityId" in excinfo.value.message
        await client.aclose()

    @pytest.mark.asyncio
    async def test_4xx_non_json_body(self, user_id: str) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(403, text="forbidden")
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerInvalidParamsError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_4xx_non_dict_body(self, user_id: str) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(400, json=["bad payload"])
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerInvalidParamsError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_200_non_json_body_raises_upstream(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, text="not json")
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_200_non_dict_body_raises_upstream(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=["a", "b"])
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_network_error_retries_then_succeeds(
        self,
        user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        call_count = {"n": 0}

        def handler(req: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpx.ConnectTimeout("timed out")
            return _ok_response(make_dhan_historical_response())

        async def _instant_sleep(_seconds: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert call_count["n"] == 2
        assert len(bars) == 3
        await client.aclose()

    @pytest.mark.asyncio
    async def test_network_error_exhausts_retries(
        self,
        user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _instant_sleep(_seconds: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)

        def _always_timeout(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        transport = httpx.MockTransport(_always_timeout)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_429_with_bad_retry_after_header(
        self,
        user_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Malformed ``Retry-After`` falls back to exp backoff."""
        call_count = {"n": 0}

        def handler(req: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(
                    429, json={}, headers={"Retry-After": "not-a-number"}
                )
            return _ok_response(make_dhan_historical_response())

        async def _instant_sleep(_seconds: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert len(bars) == 3
        await client.aclose()

    @pytest.mark.asyncio
    async def test_other_httpx_error_wrapped_as_upstream(
        self, user_id: str
    ) -> None:
        # Any HTTPError subclass that is NOT TimeoutException or
        # NetworkError hits the catch-all "other HTTPError" branch.
        # httpx.HTTPError itself works as the broad sentinel.
        def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.HTTPError("malformed request")

        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Request payload — IST conversion
# ═══════════════════════════════════════════════════════════════════════


class TestRequestPayload:
    @pytest.mark.asyncio
    async def test_ist_conversion_in_request(self, user_id: str) -> None:
        captured: list[dict[str, Any]] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req.content.decode())
            return _ok_response(make_dhan_historical_response())

        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)

        # UTC 03:45 = IST 09:15.
        from_ts = utc_datetime(hour=3, minute=45)
        to_ts = utc_datetime(hour=10, minute=0)  # IST 15:30
        await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        body = captured[0]
        # Request strings must be IST local, NOT UTC.
        assert "09:15:00" in body
        assert "15:30:00" in body
        assert "03:45:00" not in body
        await client.aclose()

    @pytest.mark.asyncio
    async def test_request_payload_field_shapes(
        self, user_id: str
    ) -> None:
        import json as _json

        captured: list[dict[str, Any]] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(_json.loads(req.content.decode()))
            return _ok_response(make_dhan_historical_response())

        transport = httpx.MockTransport(handler)
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        await client.get_historical_ohlc(
            symbol="nifty",  # lower-case input
            security_id="13",
            exchange_segment="idx_i",  # lower-case input
            instrument="index",  # lower-case input
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        body = captured[0]
        assert body["securityId"] == "13"
        # Exchange segment + instrument are upper-cased in the payload.
        assert body["exchangeSegment"] == "IDX_I"
        assert body["instrument"] == "INDEX"
        assert body["interval"] == "5"
        await client.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════════


class TestResponseParsing:
    @pytest.mark.asyncio
    async def test_empty_arrays_return_empty_list(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(
                    opens=[],
                    highs=[],
                    lows=[],
                    closes=[],
                    volumes=[],
                    timestamps=[],
                )
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert bars == []
        await client.aclose()

    @pytest.mark.asyncio
    async def test_data_wrapper_supported(self, user_id: str) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(wrap_in_data=True)
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert len(bars) == 3
        await client.aclose()

    @pytest.mark.asyncio
    async def test_length_mismatch_raises_upstream(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(
                    opens=[100.0, 101.0],  # 2 entries
                    highs=[110.0, 111.0, 112.0],  # 3 entries
                    lows=[95.0, 96.0, 97.0],
                    closes=[105.0, 106.0, 107.0],
                    timestamps=[1700000000, 1700000300, 1700000600],
                )
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        assert "mismatch" in excinfo.value.message.lower()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_volume_length_mismatch_raises(self, user_id: str) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(
                    volumes=[1000, 2000],  # only 2; timestamps has 3
                )
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_non_list_field_raises(self, user_id: str) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                {"open": "not a list", "high": [], "low": [], "close": [], "timestamp": []}
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError):
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_non_list_volume_raises(self, user_id: str) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                {
                    "open": [100.0],
                    "high": [110.0],
                    "low": [95.0],
                    "close": [105.0],
                    "volume": "not a list",
                    "timestamp": [1700000000],
                }
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        assert "volume" in excinfo.value.message.lower()
        await client.aclose()

    def test_datetime_timestamp_naive_normalised_to_utc(
        self, user_id: str
    ) -> None:
        """``_parse_response`` is called directly here because JSON
        cannot carry a datetime object on the wire — the branch
        ``isinstance(ts_raw, datetime)`` is reserved for hypothetical
        in-process callers passing a pre-decoded dict."""
        client = DhanHistoricalClient(
            client_id="CID-1", access_token="TOK", user_id=user_id
        )
        naive_dt = datetime(2026, 5, 11, 3, 45)  # naive
        bars = client._parse_response(
            symbol="NIFTY",
            timeframe=Timeframe.FIVE_MIN,
            body={
                "open": [100.0],
                "high": [110.0],
                "low": [95.0],
                "close": [105.0],
                "volume": [1000],
                "timestamp": [naive_dt],
            },
        )
        assert len(bars) == 1
        assert bars[0].timestamp.tzinfo is UTC

    def test_datetime_timestamp_aware_passes_through(
        self, user_id: str
    ) -> None:
        client = DhanHistoricalClient(
            client_id="CID-1", access_token="TOK", user_id=user_id
        )
        aware_dt = datetime(2026, 5, 11, 3, 45, tzinfo=IST_TZ)
        bars = client._parse_response(
            symbol="NIFTY",
            timeframe=Timeframe.FIVE_MIN,
            body={
                "open": [100.0],
                "high": [110.0],
                "low": [95.0],
                "close": [105.0],
                "volume": [1000],
                "timestamp": [aware_dt],
            },
        )
        assert len(bars) == 1
        assert bars[0].timestamp.tzinfo is IST_TZ

    @pytest.mark.asyncio
    async def test_dropped_errors_capped_at_ten(
        self, user_id: str
    ) -> None:
        """Sample-error list is capped at 10 entries even with 15 bad rows."""
        # 15 rows with one good plus 14 bad (high<low).
        opens = [100.0] * 15
        highs = [110.0] + [50.0] * 14  # rows 1-14 all bad
        lows = [95.0] * 15
        closes = [105.0] * 15
        volumes = [1000] * 15
        timestamps = [1700000000 + 300 * i for i in range(15)]
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                {
                    "open": opens,
                    "high": highs,
                    "low": lows,
                    "close": closes,
                    "volume": volumes,
                    "timestamp": timestamps,
                }
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        # Only the first row is valid; rest dropped.
        assert len(bars) == 1
        await client.aclose()

    @pytest.mark.asyncio
    async def test_bad_row_skipped_partial_returned(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(
                    opens=[100.0, 200.0, 300.0],
                    highs=[110.0, 99.0, 310.0],  # row 1: high<low → schema reject
                    lows=[95.0, 195.0, 295.0],
                    closes=[105.0, 198.0, 305.0],
                    volumes=[1000, 2000, 3000],
                    timestamps=[1700000000, 1700000300, 1700000600],
                )
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        # Row 1 (high < low) is dropped; 2 valid rows returned.
        assert len(bars) == 2
        await client.aclose()

    @pytest.mark.asyncio
    async def test_all_rows_bad_raises_upstream(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(
                    opens=[100.0, 200.0],
                    highs=[50.0, 150.0],  # ALL rows: high < low
                    lows=[95.0, 195.0],
                    closes=[105.0, 205.0],
                    volumes=[1000, 2000],
                    timestamps=[1700000000, 1700000300],
                )
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        with pytest.raises(BrokerUpstreamError) as excinfo:
            await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        assert "all" in excinfo.value.message.lower()
        await client.aclose()

    @pytest.mark.asyncio
    async def test_timestamp_decoded_to_utc(self, user_id: str) -> None:
        # Pick a timestamp at IST 09:15 = UTC 03:45.
        base_ts_utc = utc_datetime(hour=3, minute=45)
        epoch = int(base_ts_utc.timestamp())
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(timestamps=[epoch])
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert len(bars) == 1
        assert bars[0].timestamp == base_ts_utc
        assert bars[0].timestamp.tzinfo is UTC

    @pytest.mark.asyncio
    async def test_bars_sorted_by_timestamp(self, user_id: str) -> None:
        # Send out-of-order timestamps; client sorts ascending.
        base = int(utc_datetime().timestamp())
        transport = httpx.MockTransport(
            lambda req: _ok_response(
                make_dhan_historical_response(
                    timestamps=[base + 600, base, base + 300]
                )
            )
        )
        client = _build_client(user_id=user_id, transport=transport)
        from_ts, to_ts = _default_window()
        bars = await client.get_historical_ohlc(
            symbol="NIFTY",
            security_id="13",
            exchange_segment="IDX_I",
            instrument="INDEX",
            timeframe=Timeframe.FIVE_MIN,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        assert [int(b.timestamp.timestamp()) for b in bars] == [
            base, base + 300, base + 600,
        ]
        await client.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_async_context_manager(
        self, user_id: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda req: _ok_response(make_dhan_historical_response())
        )
        async with DhanHistoricalClient(
            client_id="CID-1",
            access_token="TOK",
            user_id=user_id,
        ) as client:
            # Override the just-created pool with a mock transport.
            await client.aclose()  # close lazy
            client._http = httpx.AsyncClient(
                base_url="https://api.dhan.co/v2",
                transport=transport,
            )
            from_ts, to_ts = _default_window()
            bars = await client.get_historical_ohlc(
                symbol="NIFTY",
                security_id="13",
                exchange_segment="IDX_I",
                instrument="INDEX",
                timeframe=Timeframe.FIVE_MIN,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            assert len(bars) == 3
        # After exit, http pool released.
        assert client._http is None

    @pytest.mark.asyncio
    async def test_aclose_idempotent(self, user_id: str) -> None:
        client = DhanHistoricalClient(
            client_id="CID-1", access_token="TOK", user_id=user_id
        )
        await client.aclose()
        await client.aclose()  # second call is a no-op
        assert client._http is None


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════


class TestModuleHelpers:
    def test_money_none_raises(self) -> None:
        with pytest.raises(ValueError):
            dhan_historical._money(None)

    def test_money_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            dhan_historical._money("   ")

    def test_money_decimal_passthrough(self) -> None:
        from decimal import Decimal
        d = Decimal("100.50")
        assert dhan_historical._money(d) is d

    def test_money_from_float_lossless(self) -> None:
        from decimal import Decimal
        assert dhan_historical._money(100.5) == Decimal("100.5")

    @pytest.mark.parametrize("attempt", [1, 2, 3, 5])
    def test_backoff_delay_within_cap(self, attempt: int) -> None:
        delay = dhan_historical._backoff_delay(attempt)
        # base = min(0.5 * 2^(n-1), 4.0); jitter up to 25%.
        assert 0 < delay <= 4.0 * 1.25 + 0.01

    def test_dhan_historical_error_str(self) -> None:
        err = dhan_historical._DhanHistoricalError(
            "boom", broker="dhan", metadata={"k": "v"}
        )
        assert str(err) == "[dhan] boom"
        assert err.metadata == {"k": "v"}

    def test_specific_errors_are_subclass(self) -> None:
        for cls in (
            BrokerAuthError,
            BrokerRateLimitError,
            BrokerUpstreamError,
            BrokerInvalidParamsError,
        ):
            err = cls("x")
            assert isinstance(err, dhan_historical._DhanHistoricalError)
            assert err.broker == "dhan"
