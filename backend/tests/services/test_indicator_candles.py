"""Tests for :mod:`app.services.indicator_candles`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.brokers.dhan_historical import (
    BrokerAuthError,
    BrokerInvalidParamsError,
    BrokerRateLimitError,
    BrokerUpstreamError,
)
from app.core import redis_client
from app.schemas.broker import BrokerCredentials, BrokerName, Exchange
from app.schemas.candle import Candle, Timeframe
from app.services import indicator_candles
from app.services.indicator_candles import (
    fetch_closed_candles,
    filter_closed_candles,
    is_candle_closed,
    resolve_dhan_credentials,
    resolve_security_id,
)
from tests.services._helpers import synthesise_candles


# ═══════════════════════════════════════════════════════════════════════
# Closed-candle filter (R1)
# ═══════════════════════════════════════════════════════════════════════


def test_is_candle_closed_at_bar_close_inclusive() -> None:
    candle = Candle(
        symbol="X",
        timeframe=Timeframe.FIVE_MIN,
        timestamp=datetime(2026, 5, 11, 9, 15, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=0,
    )
    # Bar closes at 09:20 (5m later). Exactly at close → considered closed.
    assert is_candle_closed(candle, datetime(2026, 5, 11, 9, 20, tzinfo=UTC))


def test_is_candle_closed_one_second_before_close() -> None:
    candle = Candle(
        symbol="X",
        timeframe=Timeframe.FIVE_MIN,
        timestamp=datetime(2026, 5, 11, 9, 15, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=0,
    )
    # 09:19:59 — bar still open.
    assert not is_candle_closed(
        candle, datetime(2026, 5, 11, 9, 19, 59, tzinfo=UTC)
    )


def test_filter_closed_drops_in_progress_bar() -> None:
    """Last bar is in-progress; filter excludes it."""
    candles = synthesise_candles(n=10)
    # Pin "now" to before the last bar's close (= last.timestamp + 5min).
    now = candles[-1].timestamp + timedelta(seconds=60)
    closed = filter_closed_candles(candles, now=now)
    # All but the last are closed.
    assert len(closed) == 9
    assert closed[-1].timestamp == candles[-2].timestamp


def test_filter_closed_keeps_all_when_now_past_last_close() -> None:
    candles = synthesise_candles(n=10)
    now = candles[-1].timestamp + timedelta(minutes=10)
    closed = filter_closed_candles(candles, now=now)
    assert len(closed) == 10


def test_filter_closed_returns_empty_for_all_in_progress() -> None:
    candles = synthesise_candles(n=10)
    # "Now" is before any bar has closed.
    now = candles[0].timestamp + timedelta(seconds=10)
    assert filter_closed_candles(candles, now=now) == []


# ═══════════════════════════════════════════════════════════════════════
# resolve_dhan_credentials
# ═══════════════════════════════════════════════════════════════════════


def _user_with_id(uid: str = "11111111-1111-1111-1111-111111111111") -> MagicMock:
    u = MagicMock()
    u.id = UUID(uid)
    return u


def _creds_row(*, access_token_enc: bytes | None = b"tok") -> MagicMock:
    row = MagicMock()
    row.client_id_enc = "cid"
    row.api_key_enc = "key"
    row.api_secret_enc = "secret"
    row.access_token_enc = access_token_enc
    row.refresh_token_enc = None
    row.token_expires_at = datetime(2026, 12, 31, tzinfo=UTC)
    return row


def _db_returning(row: Any) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_resolve_creds_missing_link_raises_412(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indicator_candles, "decrypt_credential", lambda v: v)
    with pytest.raises(HTTPException) as excinfo:
        await resolve_dhan_credentials(
            _user_with_id(), _db_returning(None)
        )
    assert excinfo.value.status_code == 412
    assert "broker link" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_resolve_creds_missing_token_raises_412(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indicator_candles, "decrypt_credential", lambda v: v)
    row = _creds_row(access_token_enc=None)
    with pytest.raises(HTTPException) as excinfo:
        await resolve_dhan_credentials(_user_with_id(), _db_returning(row))
    assert excinfo.value.status_code == 412
    assert "access token" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_resolve_creds_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indicator_candles, "decrypt_credential", lambda v: v)
    row = _creds_row()
    creds = await resolve_dhan_credentials(_user_with_id(), _db_returning(row))
    assert isinstance(creds, BrokerCredentials)
    assert creds.broker == BrokerName.DHAN
    assert creds.access_token == "tok"


@pytest.mark.asyncio
async def test_resolve_creds_with_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indicator_candles, "decrypt_credential", lambda v: v)
    row = _creds_row()
    row.refresh_token_enc = "refresh-bytes"
    creds = await resolve_dhan_credentials(_user_with_id(), _db_returning(row))
    assert creds.refresh_token == "refresh-bytes"


# ═══════════════════════════════════════════════════════════════════════
# resolve_security_id
# ═══════════════════════════════════════════════════════════════════════


def _creds() -> BrokerCredentials:
    return BrokerCredentials(
        broker=BrokerName.DHAN,
        user_id="u",
        client_id="C",
        api_key="K",
        api_secret="S",
        access_token="T",
    )


@pytest.mark.asyncio
async def test_resolve_security_id_happy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubBroker:
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            pass

        async def get_security_id(self, *_a: Any, **_kw: Any) -> str:
            return "11536"

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(indicator_candles, "DhanBroker", _StubBroker)
    sid = await resolve_security_id(_creds(), "NIFTY", Exchange.NSE)
    assert sid == "11536"


@pytest.mark.asyncio
async def test_resolve_security_id_lookup_fails_raises_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BadBroker:
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            pass

        async def get_security_id(self, *_a: Any, **_kw: Any) -> str:
            raise RuntimeError("not in master")

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(indicator_candles, "DhanBroker", _BadBroker)
    with pytest.raises(HTTPException) as excinfo:
        await resolve_security_id(_creds(), "BOGUS", Exchange.NSE)
    assert excinfo.value.status_code == 404
    assert "scrip master" in excinfo.value.detail.lower()


# ═══════════════════════════════════════════════════════════════════════
# fetch_closed_candles end-to-end
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def _fake_redis(monkeypatch: pytest.MonkeyPatch):
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


def _stub_creds_resolver() -> Any:
    async def _r(_user: Any, _db: Any) -> BrokerCredentials:
        return _creds()
    return _r


def _stub_sid_resolver(sid: str = "13") -> Any:
    async def _r(*_a: Any, **_kw: Any) -> str:
        return sid
    return _r


def _stub_client_factory(candles: list[Candle] | Exception):
    class _Stub:
        def __init__(self, **_kw: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *_exc: Any) -> None:
            pass

        async def get_historical_ohlc(self, **_kw: Any) -> list[Candle]:
            if isinstance(candles, Exception):
                raise candles
            return list(candles)

    return _Stub


@pytest.mark.asyncio
async def test_fetch_closed_candles_happy_path() -> None:
    src_candles = synthesise_candles(n=200)
    now = src_candles[-1].timestamp + timedelta(minutes=10)
    out = await fetch_closed_candles(
        user=_user_with_id(),
        db=AsyncMock(),
        symbol="NIFTY",
        exchange=Exchange.NSE,
        timeframe=Timeframe.FIVE_MIN,
        from_ts=src_candles[0].timestamp,
        to_ts=src_candles[-1].timestamp,
        now=lambda: now,
        creds_resolver=_stub_creds_resolver(),
        security_id_resolver=_stub_sid_resolver(),
        historical_client_factory=_stub_client_factory(src_candles),
    )
    assert len(out) == 200


@pytest.mark.asyncio
async def test_fetch_closed_filters_in_progress_bar() -> None:
    src_candles = synthesise_candles(n=10)
    # Pin "now" within the last bar's window.
    now = src_candles[-1].timestamp + timedelta(seconds=30)
    out = await fetch_closed_candles(
        user=_user_with_id(),
        db=AsyncMock(),
        symbol="NIFTY",
        exchange=Exchange.NSE,
        timeframe=Timeframe.FIVE_MIN,
        from_ts=src_candles[0].timestamp,
        to_ts=src_candles[-1].timestamp,
        now=lambda: now,
        creds_resolver=_stub_creds_resolver(),
        security_id_resolver=_stub_sid_resolver(),
        historical_client_factory=_stub_client_factory(src_candles),
    )
    assert len(out) == 9


@pytest.mark.asyncio
async def test_fetch_closed_unsupported_exchange_raises_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every Exchange enum value is mapped today; to exercise the
    "no segment" branch we drop NSE from the map via monkeypatch."""
    monkeypatch.setattr(indicator_candles, "_EXCHANGE_TO_SEGMENT", {})
    src_candles = synthesise_candles(n=10)
    with pytest.raises(HTTPException) as excinfo:
        await fetch_closed_candles(
            user=_user_with_id(),
            db=AsyncMock(),
            symbol="X",
            exchange=Exchange.NSE,
            timeframe=Timeframe.FIVE_MIN,
            from_ts=src_candles[0].timestamp,
            to_ts=src_candles[-1].timestamp,
            creds_resolver=_stub_creds_resolver(),
            security_id_resolver=_stub_sid_resolver(),
            historical_client_factory=_stub_client_factory(src_candles),
        )
    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc_cls", "expected_status"),
    [
        (BrokerAuthError("auth"), 401),
        (BrokerInvalidParamsError("bad"), 400),
        (BrokerRateLimitError("rate"), 429),
        (BrokerUpstreamError("upstream"), 502),
    ],
)
async def test_broker_errors_mapped_to_http(
    exc_cls: Exception, expected_status: int
) -> None:
    src_candles = synthesise_candles(n=10)
    with pytest.raises(HTTPException) as excinfo:
        await fetch_closed_candles(
            user=_user_with_id(),
            db=AsyncMock(),
            symbol="NIFTY",
            exchange=Exchange.NSE,
            timeframe=Timeframe.FIVE_MIN,
            from_ts=src_candles[0].timestamp,
            to_ts=src_candles[-1].timestamp,
            creds_resolver=_stub_creds_resolver(),
            security_id_resolver=_stub_sid_resolver(),
            historical_client_factory=_stub_client_factory(exc_cls),
        )
    assert excinfo.value.status_code == expected_status
