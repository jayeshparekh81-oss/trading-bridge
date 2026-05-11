"""Candle source helper for the indicator service.

Resolves a user's Dhan credentials, fetches OHLC candles for the
requested window via :class:`DhanHistoricalClient`, and filters the
result to **closed candles only** (R1 — see
``project_indicator_sprint.md`` in memory).

A candle is "closed" when its bar-close time (= ``timestamp +
timeframe.seconds``) is at or before the server's current time. The
in-progress (current) bar is excluded because its OHLC is still
ticking; caching by ``last_closed_candle_ts`` only works if the
underlying candle is immutable.

This module duplicates the small amount of credential-resolution +
scrip-master lookup logic from :mod:`app.api.chart` so the
indicator service has zero coupling to the chart route's import
surface — both must stay editable independently per the parallel-CC
coordination rule. Phase 2 will dedupe into a shared
``services/chart_data.py`` (flagged in
``PATCH_INSTRUCTIONS_INDICATORS.md``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.dhan import DhanBroker
from app.brokers.dhan_historical import (
    BrokerAuthError,
    BrokerInvalidParamsError,
    BrokerRateLimitError,
    BrokerUpstreamError,
    DhanHistoricalClient,
)
from app.core.logging import get_logger
from app.core.security import decrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.user import User
from app.schemas.broker import BrokerCredentials, BrokerName, Exchange
from app.schemas.candle import Candle, Timeframe


_logger = get_logger("services.indicator_candles")


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════
#
# Mirrors of the maps in app/api/chart.py — duplicated rather than
# imported per the parallel-CC isolation rule.

_EXCHANGE_TO_SEGMENT: dict[Exchange, str] = {
    Exchange.NSE: "NSE_EQ",
    Exchange.BSE: "BSE_EQ",
    Exchange.NFO: "NSE_FNO",
    Exchange.BFO: "BSE_FNO",
    Exchange.MCX: "MCX_COMM",
    Exchange.CDS: "NSE_CURRENCY",
}

_SEGMENT_TO_INSTRUMENT: dict[str, str] = {
    "NSE_EQ": "EQUITY",
    "BSE_EQ": "EQUITY",
    "NSE_FNO": "FUTIDX",
    "BSE_FNO": "FUTIDX",
    "MCX_COMM": "FUTCOM",
    "NSE_CURRENCY": "FUTCUR",
    "IDX_I": "INDEX",
}


# ═══════════════════════════════════════════════════════════════════════
# R1 — closed-candle filter
# ═══════════════════════════════════════════════════════════════════════


def is_candle_closed(candle: Candle, now: datetime) -> bool:
    """A candle is closed when its bar's close time ≤ ``now``.

    Bar close time is ``candle.timestamp + timeframe.seconds`` —
    Candle.timestamp is bar-OPEN time by convention across the chart
    module.
    """
    bar_close = candle.timestamp + timedelta(seconds=candle.timeframe.seconds)
    return bar_close <= now


def filter_closed_candles(
    candles: list[Candle], *, now: datetime
) -> list[Candle]:
    """Return only candles whose bar has closed at ``now``.

    Pure function — used by the orchestrator after fetching from
    Dhan. ``now`` is passed in (not read from ``datetime.now``) so
    tests can pin the clock without monkeypatching globals.
    """
    return [c for c in candles if is_candle_closed(c, now)]


# ═══════════════════════════════════════════════════════════════════════
# Credential + symbol resolution
# ═══════════════════════════════════════════════════════════════════════


async def resolve_dhan_credentials(
    user: User, db: AsyncSession
) -> BrokerCredentials:
    """Fetch the active Dhan ``BrokerCredential`` for ``user``, decrypt,
    return a populated :class:`BrokerCredentials`.

    Raises:
        HTTPException 412: User has no active Dhan link or the access
            token has been wiped.
    """
    stmt = select(BrokerCredential).where(
        BrokerCredential.user_id == user.id,
        BrokerCredential.broker_name == BrokerName.DHAN,
        BrokerCredential.is_active.is_(True),
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                "Indicators ke liye Dhan broker link chahiye — "
                "pehle apna Dhan account connect karo."
            ),
        )
    if not row.access_token_enc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                "Dhan access token missing — broker session reconnect karo "
                "to indicators compute ho sake."
            ),
        )
    return BrokerCredentials(
        broker=BrokerName.DHAN,
        user_id=str(user.id),
        client_id=decrypt_credential(row.client_id_enc),
        api_key=decrypt_credential(row.api_key_enc),
        api_secret=decrypt_credential(row.api_secret_enc),
        access_token=decrypt_credential(row.access_token_enc),
        refresh_token=(
            decrypt_credential(row.refresh_token_enc)
            if row.refresh_token_enc
            else None
        ),
        token_expires_at=row.token_expires_at,
    )


async def resolve_security_id(
    creds: BrokerCredentials, symbol: str, exchange: Exchange
) -> str:
    """Look up the Dhan numeric security_id via a transient
    :class:`DhanBroker` — same one-shot pattern the chart route uses.

    Raises:
        HTTPException 404: Symbol absent from the scrip master.
    """
    broker = DhanBroker(creds)
    try:
        return await broker.get_security_id(symbol, exchange)
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "indicators.security_id_resolution_failed",
            symbol=symbol,
            exchange=exchange.value,
            error=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Symbol {symbol!r} Dhan scrip master mein nahi mila. "
                "Spelling aur exchange dono confirm karo."
            ),
        ) from exc
    finally:
        await broker.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Top-level fetcher
# ═══════════════════════════════════════════════════════════════════════


async def fetch_closed_candles(
    *,
    user: User,
    db: AsyncSession,
    symbol: str,
    exchange: Exchange,
    timeframe: Timeframe,
    from_ts: datetime,
    to_ts: datetime,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    creds_resolver: Callable[..., object] | None = None,
    security_id_resolver: Callable[..., object] | None = None,
    historical_client_factory: Callable[..., object] | None = None,
) -> list[Candle]:
    """End-to-end fetcher used by the indicator orchestrator.

    Resolves credentials → resolves security_id → fetches via
    :class:`DhanHistoricalClient` → filters to closed candles only.
    The four optional ``*_resolver`` / ``*_factory`` parameters are
    test seams.

    Broker-side errors are mapped onto matching HTTP status codes
    (same mapping the chart route uses) so the API route just
    re-raises whatever this returns.
    """
    creds_fn = creds_resolver or resolve_dhan_credentials
    sid_fn = security_id_resolver or resolve_security_id
    client_factory = historical_client_factory or DhanHistoricalClient

    creds = await creds_fn(user, db)
    segment = _EXCHANGE_TO_SEGMENT.get(exchange)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exchange {exchange.value} indicators mein supported nahi hai.",
        )
    instrument = _SEGMENT_TO_INSTRUMENT.get(segment, "EQUITY")

    security_id = await sid_fn(creds, symbol, exchange)

    try:
        async with client_factory(
            client_id=creds.client_id,
            access_token=creds.access_token or "",
            user_id=str(user.id),
        ) as client:
            candles = await client.get_historical_ohlc(
                symbol=symbol,
                security_id=security_id,
                exchange_segment=segment,
                instrument=instrument,
                timeframe=timeframe,
                from_ts=from_ts,
                to_ts=to_ts,
            )
    except BrokerAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message
        ) from exc
    except BrokerInvalidParamsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except BrokerRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.message
        ) from exc
    except BrokerUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message
        ) from exc

    return filter_closed_candles(candles, now=now())


__all__ = [
    "fetch_closed_candles",
    "filter_closed_candles",
    "is_candle_closed",
    "resolve_dhan_credentials",
    "resolve_security_id",
]
