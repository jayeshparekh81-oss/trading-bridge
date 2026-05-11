"""Chart-module HTTP + WebSocket API surface.

Three routes mounted under one FastAPI ``APIRouter``:

* ``GET  /api/chart/history``         — historical OHLC, 5-min Redis cache.
* ``GET  /api/chart/ws-token``        — issue 15-min JWT for the live WS.
* ``WS   /ws/chart/{symbol}/{timeframe}`` — live candle + control stream.

Coordination (new-files-only rule)
----------------------------------
This module *does* import — read-only — from a handful of existing
modules: :mod:`app.api.deps`, :mod:`app.core.security`,
:mod:`app.core.security_ext`, :mod:`app.core.redis_client`,
:mod:`app.db.models.broker_credential`, :mod:`app.schemas.broker`, and
:mod:`app.brokers.dhan` (for one read-only call:
:meth:`DhanBroker.get_security_id`). It does NOT modify any of them.

The :class:`DhanBroker` import is the one external dependency that the
parallel CC session could conceivably move under our feet — it's the
existing REST adapter that they are working on. Mitigation:

* We only call :meth:`DhanBroker.get_security_id` and
  :meth:`DhanBroker.aclose`, both of which are part of the stable
  :class:`BrokerInterface` contract.
* Every test mocks this call so test breakage from upstream signature
  changes is contained.
* Phase 2 will extract the symbol-resolution concern into a shared
  ``SymbolResolver`` service — flagged in ``PATCH_INSTRUCTIONS.md``.

main.py wiring (Jayesh applies manually)
----------------------------------------
Add the following two lines to ``backend/app/main.py``::

    from app.api.chart import router as chart_router  # noqa: E402
    app.include_router(chart_router)

Place the ``include_router`` next to the other ``app.include_router``
calls; ordering does not matter because the routes are
non-overlapping. A single router serves both the HTTP and WebSocket
endpoints, so only one ``include_router`` call is needed.

Endpoint semantics
------------------

**GET /api/chart/history**

Query parameters:
    * ``symbol``    — trading symbol (upper-cased automatically).
    * ``exchange``  — :class:`~app.schemas.broker.Exchange` enum value.
    * ``timeframe`` — :class:`~app.schemas.candle.Timeframe` enum value.
    * ``from``      — ISO 8601 with tz offset (inclusive).
    * ``to``        — ISO 8601 with tz offset (inclusive).

Returns a :class:`ChartHistoryResponse`. On cache hit, ``cached=True``
in the response. On miss we resolve the user's decrypted Dhan
credentials, look up the security_id via the existing scrip master,
hit Dhan's historical endpoint via :class:`DhanHistoricalClient`, and
cache the full JSON for 5 minutes.

**GET /api/chart/ws-token**

Issues a short-lived JWT (15 min, ``ttl_seconds=900``) for the live
WebSocket. The frontend is expected to refresh every 12 min — the
3-min grace window covers clock skew + network roundtrips.

The token is a vanilla ``create_session_token`` JWT for v1; a future
enhancement will add an ``aud="ws"`` claim to scope it more tightly
(flagged in ``PATCH_INSTRUCTIONS.md``).

**WS /ws/chart/{symbol}/{timeframe}**

Connect with ``?token=<jwt>``. The server validates the token (no
fingerprint check, because the WS handshake may carry slightly
different headers than the HTTP request that minted the token), then
subscribes to:

    * ``chart:candles:{symbol}:{timeframe}`` — aggregated OHLC bars
    * ``chart:control:{symbol}``             — disconnect / reconnect events

Every message is wrapped in a ``{"event": <type>, ...}`` envelope so
the frontend can switch on event type. Heartbeat frames
(``{"event": "heartbeat", "at": <iso>}``) flow every 15s of silence
to keep proxies + browser tabs awake.

Error mapping (REST endpoint)
-----------------------------
:class:`DhanHistoricalClient` raises module-local typed errors; we map
each to the appropriate HTTP status:

    BrokerAuthError          → 401  (route layer also emits a hint to re-link)
    BrokerInvalidParamsError → 400
    BrokerRateLimitError     → 429
    BrokerUpstreamError      → 502

User-facing ``detail`` strings preserve the Hinglish message from the
exception when applicable.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.brokers.dhan import DhanBroker
from app.brokers.dhan_historical import (
    BrokerAuthError,
    BrokerInvalidParamsError,
    BrokerRateLimitError,
    BrokerUpstreamError,
    DhanHistoricalClient,
)
from app.core.logging import bind_request_context, get_logger
from app.core.redis_client import cache_get, cache_set
from app.core.security import decrypt_credential
from app.core.security_ext import (
    create_session_token,
    generate_session_fingerprint,
    validate_session_token,
)
from app.db.models.broker_credential import BrokerCredential
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.broker import BrokerCredentials, BrokerName, Exchange
from app.schemas.candle import (
    ChartEventType,
    ChartHistoryResponse,
    Timeframe,
)
from app.services.chart_redis import (
    chart_candles_channel,
    chart_control_channel,
    get_next_message,
    subscribe,
)


_logger = get_logger("api.chart")


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════


#: Historical-response cache TTL in seconds. 5 minutes balances staleness
#: vs Dhan rate-limit headroom — a chart user usually pans + zooms within
#: this window and the cache hit cuts Dhan load by an order of magnitude.
_HISTORY_CACHE_TTL_S = 300

#: WebSocket auth token lifetime. Frontend should refresh at 12 min to
#: leave a 3-min grace window for clock skew + network jitter.
_WS_TOKEN_TTL_S = 900

#: How long the live WS will sit silent before sending a heartbeat. 15s
#: is well under the typical 30s proxy idle-timeout and keeps mobile
#: browsers from backgrounding the tab.
_WS_HEARTBEAT_INTERVAL_S = 15.0

#: Pub/sub read timeout per loop iteration. Tight enough that heartbeats
#: fire on time, loose enough that we don't burn CPU spin-looping.
_WS_POLL_TIMEOUT_S = 1.0

#: Exchange enum → Dhan exchange-segment string. Inlined (not imported
#: from brokers/dhan.py) so the dependency arrow into ``dhan.py`` is
#: limited to the one explicit ``get_security_id`` call.
_EXCHANGE_TO_SEGMENT: dict[Exchange, str] = {
    Exchange.NSE: "NSE_EQ",
    Exchange.BSE: "BSE_EQ",
    Exchange.NFO: "NSE_FNO",
    Exchange.BFO: "BSE_FNO",
    Exchange.MCX: "MCX_COMM",
    Exchange.CDS: "NSE_CURRENCY",
}

#: Heuristic segment → Dhan ``instrument`` field. v1 simplification:
#: FNO segments default to ``FUTIDX``. Phase 2 needs proper detection
#: (FUTSTK vs FUTIDX vs OPTIDX vs OPTSTK requires symbol parsing) —
#: flagged in PATCH_INSTRUCTIONS.md.
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
# Inline response schema
# ═══════════════════════════════════════════════════════════════════════


class WsTokenResponse(BaseModel):
    """Response shape for ``GET /api/chart/ws-token``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: str = Field(..., min_length=1)
    expires_in: int = Field(..., gt=0, description="Token lifetime in seconds.")


# ═══════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════


#: Single router serves both the ``/api/chart/*`` HTTP routes and the
#: ``/ws/chart/...`` WebSocket route. Mounting via one
#: ``app.include_router(router)`` call in main.py keeps the wiring
#: comment short (see module docstring).
router = APIRouter(tags=["chart"])


# ═══════════════════════════════════════════════════════════════════════
# Credential + symbol resolution
# ═══════════════════════════════════════════════════════════════════════


async def _resolve_dhan_credentials(
    user: User, db: AsyncSession
) -> BrokerCredentials:
    """Fetch + decrypt the user's active Dhan ``BrokerCredentials``.

    Mirrors :func:`app.services.order_service._build_broker_credentials`
    so the encrypted-column → decrypted-value mapping stays consistent
    across order flow and chart flow.

    Raises:
        HTTPException 412: User has no active Dhan link, or the access
            token has been wiped (e.g. expired & not yet relinked).
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
                "Dhan broker link nahi mila — chart dekhne ke liye pehle "
                "apna Dhan account connect karna padega."
            ),
        )
    if not row.access_token_enc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                "Dhan access token missing — apni Dhan session reconnect karo "
                "to chart history load ho sake."
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


async def _resolve_security_id(
    creds: BrokerCredentials, symbol: str, exchange: Exchange
) -> str:
    """Look up Dhan numeric securityId via the existing scrip master.

    Instantiates a transient :class:`DhanBroker` just for the read-only
    ``get_security_id`` call. This is the **only** point where chart
    code touches the existing Dhan REST adapter — Phase 2 should extract
    a standalone ``SymbolResolver`` service so this dependency goes away
    (see ``PATCH_INSTRUCTIONS.md``).

    Raises:
        HTTPException 404: Symbol not in Dhan's scrip master (delisted,
            typo, wrong segment).
    """
    broker = DhanBroker(creds)
    try:
        return await broker.get_security_id(symbol, exchange)
    except Exception as exc:
        _logger.warning(
            "chart.history.security_id_resolution_failed",
            symbol=symbol,
            exchange=exchange.value,
            error=type(exc).__name__,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Symbol {symbol!r} Dhan scrip master mein nahi mila. "
                "Symbol spelling aur exchange dono confirm karo."
            ),
        ) from exc
    finally:
        await broker.aclose()


def _history_cache_key(
    symbol: str, timeframe: Timeframe, from_ts: datetime, to_ts: datetime
) -> str:
    """Deterministic cache key for ``GET /api/chart/history`` responses.

    Epoch-second buckets in the key (not ISO strings) so two callers
    asking for the same window with different timezone formatting
    still hit the same cache entry.
    """
    return (
        f"chart_history:{symbol.upper()}:{timeframe.value}:"
        f"{int(from_ts.timestamp())}:{int(to_ts.timestamp())}"
    )


# ═══════════════════════════════════════════════════════════════════════
# Endpoint: GET /api/chart/history
# ═══════════════════════════════════════════════════════════════════════


@router.get("/api/chart/history", response_model=ChartHistoryResponse)
async def get_chart_history(
    symbol: str = Query(..., min_length=1, max_length=64),
    exchange: Exchange = Query(...),
    timeframe: Timeframe = Query(...),
    from_ts: datetime = Query(..., alias="from"),
    to_ts: datetime = Query(..., alias="to"),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> ChartHistoryResponse:
    """Fetch historical OHLC bars with a 5-minute Redis cache.

    See module docstring for the full contract. Errors from the
    underlying :class:`DhanHistoricalClient` are mapped onto the
    appropriate HTTP status codes (auth → 401, params → 400, rate →
    429, upstream → 502).
    """
    bind_request_context(user_id=str(user.id), symbol=symbol.upper())

    if from_ts.tzinfo is None or to_ts.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "from + to dono ISO 8601 timezone-aware hone chahiye "
                "(e.g. 2024-01-01T09:15:00+05:30)."
            ),
        )

    sym = symbol.strip().upper()
    cache_key = _history_cache_key(sym, timeframe, from_ts, to_ts)

    cached_str = await cache_get(cache_key)
    if cached_str is not None:
        # CRITICAL: model_validate_json (NOT json.loads + model_validate) —
        # strict mode in our schemas rejects "42.5" → Decimal in dict
        # form but accepts it in JSON form. See
        # services/chart_redis.py READ-SIDE CONTRACT for the gory detail.
        try:
            cached_resp = ChartHistoryResponse.model_validate_json(cached_str)
            return cached_resp.model_copy(update={"cached": True})
        except ValidationError:
            _logger.warning(
                "chart.history.cache_corrupt",
                cache_key=cache_key,
                symbol=sym,
            )
            # Fall through to a fresh fetch; cache will be overwritten.

    segment = _EXCHANGE_TO_SEGMENT.get(exchange)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exchange {exchange.value} chart module mein supported nahi hai.",
        )
    instrument = _SEGMENT_TO_INSTRUMENT.get(segment, "EQUITY")

    creds = await _resolve_dhan_credentials(user, db)
    security_id = await _resolve_security_id(creds, sym, exchange)

    try:
        async with DhanHistoricalClient(
            client_id=creds.client_id,
            access_token=creds.access_token or "",
            user_id=str(user.id),
        ) as client:
            candles = await client.get_historical_ohlc(
                symbol=sym,
                security_id=security_id,
                exchange_segment=segment,
                instrument=instrument,
                timeframe=timeframe,
                from_ts=from_ts,
                to_ts=to_ts,
            )
    except BrokerAuthError as exc:
        # 401 with Hinglish: frontend catches this + triggers re-link UI,
        # mirroring the BROKER_DISCONNECTED flow used by the WS path.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc
    except BrokerInvalidParamsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    except BrokerRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.message,
        ) from exc
    except BrokerUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        ) from exc

    response = ChartHistoryResponse(
        symbol=sym,
        timeframe=timeframe,
        from_ts=from_ts,
        to_ts=to_ts,
        cached=False,
        candles=candles,
    )

    try:
        await cache_set(
            cache_key,
            response.model_dump_json(),
            ttl_seconds=_HISTORY_CACHE_TTL_S,
        )
    except Exception as exc:  # noqa: BLE001
        # A cache write failure must NEVER fail the request. Log + carry on.
        _logger.warning(
            "chart.history.cache_set_failed",
            cache_key=cache_key,
            error=type(exc).__name__,
        )

    return response


# ═══════════════════════════════════════════════════════════════════════
# Endpoint: GET /api/chart/ws-token
# ═══════════════════════════════════════════════════════════════════════


@router.get("/api/chart/ws-token", response_model=WsTokenResponse)
async def get_chart_ws_token(
    request: Request,
    user: User = Depends(get_current_active_user),
) -> WsTokenResponse:
    """Issue a short-lived (15-min) JWT for the live chart WebSocket.

    Frontend should call this immediately before opening the WS and
    refresh every 12 minutes thereafter. The token uses the standard
    :func:`app.core.security_ext.create_session_token` infrastructure;
    a future enhancement will add an ``aud="ws"`` claim for tighter
    scoping — see ``PATCH_INSTRUCTIONS.md``.
    """
    fingerprint = generate_session_fingerprint(
        user_agent=request.headers.get("User-Agent", ""),
        ip=request.client.host if request.client else "",
        accept_language=request.headers.get("Accept-Language", ""),
        accept_encoding=request.headers.get("Accept-Encoding", ""),
    )
    token = create_session_token(
        user_id=str(user.id),
        fingerprint=fingerprint,
        ttl_seconds=_WS_TOKEN_TTL_S,
    )
    return WsTokenResponse(token=token, expires_in=_WS_TOKEN_TTL_S)


# ═══════════════════════════════════════════════════════════════════════
# Endpoint: WS /ws/chart/{symbol}/{timeframe}
# ═══════════════════════════════════════════════════════════════════════


@router.websocket("/ws/chart/{symbol}/{timeframe}")
async def chart_ws(
    websocket: WebSocket,
    symbol: str,
    timeframe: str,
) -> None:
    """Live candle + control-event stream for one ``(symbol, timeframe)``.

    Auth: ``?token=<jwt>`` query string. Validation is timezone- and
    fingerprint-independent (a 15-min TTL is the binding security
    primitive). Invalid token → close code ``4401``.

    Subscribes to two Redis pub/sub channels:
        * ``chart:candles:{symbol}:{timeframe}`` — aggregated bars
        * ``chart:control:{symbol}``             — disconnect events

    Forwards each message as a JSON envelope to the browser.
    Sends a ``{"event": "heartbeat", ...}`` frame every 15s of silence.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(
            code=4401, reason="Missing ?token query param."
        )
        return

    claims = await validate_session_token(token, current_fingerprint=None)
    if claims is None:
        await websocket.close(code=4401, reason="Invalid or expired ws-token.")
        return

    user_id_str = str(claims.get("sub") or "")

    try:
        tf = Timeframe(timeframe)
    except ValueError:
        await websocket.close(
            code=4400,
            reason=f"Unknown timeframe: {timeframe!r}.",
        )
        return

    # ``chart_*_channel`` helpers run the same regex-based symbol
    # validation that the WS adapter uses for publishing. A bad symbol
    # raises ``ValueError``, which we translate into a 4400 close.
    try:
        candles_channel = chart_candles_channel(symbol, tf.value)
        control_channel = chart_control_channel(symbol)
    except ValueError as exc:
        await websocket.close(code=4400, reason=str(exc))
        return

    bind_request_context(
        user_id=user_id_str,
        symbol=symbol.upper(),
        timeframe=tf.value,
    )

    await websocket.accept()
    _logger.info(
        "chart.ws.accepted",
        candles_channel=candles_channel,
        control_channel=control_channel,
    )

    pubsub = await subscribe(candles_channel, control_channel)
    last_send = asyncio.get_event_loop().time()

    try:
        while True:
            msg = await get_next_message(pubsub, timeout=_WS_POLL_TIMEOUT_S)
            now = asyncio.get_event_loop().time()

            if msg is None:
                if now - last_send >= _WS_HEARTBEAT_INTERVAL_S:
                    await websocket.send_json(
                        {
                            "event": ChartEventType.HEARTBEAT.value,
                            "at": datetime.now(UTC).isoformat(),
                        }
                    )
                    last_send = now
                continue

            envelope = _envelope_for(msg)
            if envelope is None:
                # Malformed pub/sub payload — logged inside _envelope_for.
                continue

            await websocket.send_json(envelope)
            last_send = now

    except WebSocketDisconnect:
        _logger.info("chart.ws.client_disconnected")
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "chart.ws.unexpected_error",
            error=type(exc).__name__,
            error_message=str(exc),
        )
        try:
            await websocket.close(code=1011, reason="Server error.")
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await pubsub.unsubscribe(candles_channel, control_channel)
        except Exception:  # noqa: BLE001
            pass
        try:
            await pubsub.aclose()
        except Exception:  # noqa: BLE001
            pass


# ═══════════════════════════════════════════════════════════════════════
# WebSocket envelope formatter
# ═══════════════════════════════════════════════════════════════════════


def _envelope_for(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Translate one raw Redis pub/sub message into the browser envelope.

    Control-channel payloads (``BrokerDisconnectedEvent``,
    ``BrokerReconnectedEvent``) already carry an ``"event"`` field
    matching :class:`ChartEventType`, so we forward them as-is.

    Candle-channel payloads are bare :class:`Candle` dicts — we wrap
    them under ``{"event": "candle", "data": {...}}`` so the frontend
    can dispatch on the same discriminator for every frame.

    Returns ``None`` for un-parseable payloads (logged at WARN).
    """
    data = msg.get("data")
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            _logger.warning(
                "chart.ws.bad_payload_encoding", channel=msg.get("channel")
            )
            return None
    if not isinstance(data, str):
        _logger.warning(
            "chart.ws.bad_payload_type",
            channel=msg.get("channel"),
            type=type(data).__name__,
        )
        return None

    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        _logger.warning(
            "chart.ws.bad_payload_json", channel=msg.get("channel")
        )
        return None

    if isinstance(payload, dict) and "event" in payload:
        return payload
    return {"event": ChartEventType.CANDLE.value, "data": payload}


__all__ = ["router", "WsTokenResponse"]
