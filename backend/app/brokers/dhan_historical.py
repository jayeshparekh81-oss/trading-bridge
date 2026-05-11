"""Self-contained Dhan HQ v2 historical OHLC client.

Used by the chart module's ``GET /api/chart/history`` endpoint to fetch
candles when the 5-min Redis cache misses. Lives in its own module per
the chart-branch coordination rule — does NOT import from
:mod:`app.brokers.dhan` (the existing REST adapter), so concurrent work
on ``brokers/dhan.py`` from a parallel CC session cannot create a merge
conflict.

**Per-user instantiation.** Route layer owns credential resolution.
Do not cache instances across users. Each request resolves the calling
user's decrypted ``BrokerCredentials`` (mirroring ``api/brokers.py``)
and builds a fresh :class:`DhanHistoricalClient` for that request. The
HTTP pool inside the client is per-instance — for v1 we accept one
``httpx.AsyncClient`` per request rather than a shared pool. The
connection-pool refactor is flagged in ``PATCH_INSTRUCTIONS.md``.

**Supported timeframes (Dhan v2 historical):**
    ``1m``, ``5m``, ``15m``, ``1h``, ``1d``.

    Other :class:`~app.schemas.candle.Timeframe` values (``3m``,
    ``30m``) raise :class:`BrokerInvalidParamsError` — Dhan's
    ``/charts/intraday`` endpoint does not natively accept those
    intervals. Phase 2 will add server-side downsampling (see
    ``PATCH_INSTRUCTIONS.md``).

**Date range guards (per Dhan limits):**
    * Intraday timeframes: ≤ 90 days per request.
    * Daily: ≤ 5 years per request.
    * Exceed → :class:`BrokerInvalidParamsError`. v1 does not chunk
      automatically — Phase 2 work (see ``PATCH_INSTRUCTIONS.md``).

**Rate limiting (Dhan historical: 5 req/sec per access-token):**
    * Local pre-flight check via :func:`app.core.redis_client.rate_limit_check`
      keyed per-user (``rate:dhan_historical:{user_id}``) — Dhan's
      5 req/s is per-token, so global keying would cause catastrophic
      contention at scale.
    * On local block: short async sleep (≤1s), one retry, then raise
      :class:`BrokerRateLimitError`. No infinite retry loop.
    * Reactive layer: on Dhan-side ``429`` or ``5xx`` responses,
      exponential backoff with jitter, max 3 attempts total.

**Auth + 401 contract:**
    * Auth headers per Dhan v2: ``client-id`` and ``access-token``.
    * ``401`` from Dhan → :class:`BrokerAuthError`. The chart route
      catches this, emits a ``BROKER_DISCONNECTED`` event over the live
      WS, and the frontend re-prompts the user to refresh their broker
      session. Same contract Fyers' 2:39 AM session expiry will use.

**Local typed errors.** This module defines its own error hierarchy
rather than importing from :mod:`app.core.exceptions`. Same reason as
above: parallel session may be editing that module. The names
intentionally mirror the global hierarchy so a future consolidation
into ``app/brokers/errors.py`` is a mechanical rename — see
``PATCH_INSTRUCTIONS.md``. Callers must import the error classes from
THIS module:

    from app.brokers.dhan_historical import BrokerAuthError, ...

Yahan har request fresh client banata hai with per-user credentials.
Token rotation, scrip-master ka lookup, security_id resolution — sab
route layer ka kaam hai; ye module sirf HTTP-level OHLC fetch karta hai.
"""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from types import TracebackType
from typing import Any
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.core.logging import get_logger
from app.core.redis_client import rate_limit_check
from app.schemas.candle import Candle, Timeframe


_logger = get_logger("brokers.dhan_historical")


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════


#: Dhan v2 REST base URL. Kept inline here per new-files-only rule —
#: PATCH_INSTRUCTIONS notes the future move to ``Settings.dhan_api_base_url``.
_DHAN_BASE_URL = "https://api.dhan.co/v2"

#: Endpoint paths. Dhan v2 splits intraday vs daily into separate routes.
#: Verified against Dhan v2 published API as of 2026-05-11; operator
#: should sanity-check against the current Dhan swagger before deploy —
#: noted in PATCH_INSTRUCTIONS.md.
_INTRADAY_PATH = "/charts/intraday"
_HISTORICAL_PATH = "/charts/historical"

#: Total request timeout including connect + read. Dhan historicals
#: typically respond in <2s; 10s is generous headroom for a slow VPS link.
_HTTP_TIMEOUT_SECONDS = 10.0
_HTTP_CONNECT_TIMEOUT = 5.0

#: Reactive retry budget for 429 / 5xx / transport-level failures.
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_S = 0.5
_RETRY_MAX_DELAY_S = 4.0

#: Local rate-limit cap (Dhan: 5 req/sec for historical, per access-token).
_LOCAL_RATE_MAX = 5
_LOCAL_RATE_WINDOW_S = 1
#: How long the client will sleep + retry once on a local rate-limit hit
#: before giving up and raising. Keeps p99 latency bounded.
_LOCAL_RATE_RETRY_SLEEP_S = 1.0

#: IST is UTC+5:30 with no DST — fixed offset is correct and avoids
#: pulling in zoneinfo + tzdata as a runtime dependency. Used for
#: ``fromDate``/``toDate`` request formatting which Dhan documents as
#: IST local time.
_IST = timezone(timedelta(hours=5, minutes=30))

#: Map our :class:`Timeframe` enum onto Dhan's ``interval`` vocabulary.
#: Intentionally a strict subset — :class:`Timeframe.THREE_MIN` and
#: :class:`Timeframe.THIRTY_MIN` are deliberately absent because Dhan's
#: ``/charts/intraday`` endpoint does not natively accept ``"3"`` or
#: ``"30"`` (per Dhan v2 spec; intraday accepts 1/5/15/25/60 minute
#: buckets only). A KeyError on lookup is reraised as
#: :class:`BrokerInvalidParamsError` — fail fast at the API boundary.
_TIMEFRAME_TO_DHAN: dict[Timeframe, str] = {
    Timeframe.ONE_MIN: "1",
    Timeframe.FIVE_MIN: "5",
    Timeframe.FIFTEEN_MIN: "15",
    Timeframe.ONE_HOUR: "60",
    Timeframe.ONE_DAY: "D",
}

#: Timeframes routed to /charts/intraday. Everything else (daily) goes
#: to /charts/historical with no ``interval`` field.
_INTRADAY_TIMEFRAMES: frozenset[Timeframe] = frozenset(
    {
        Timeframe.ONE_MIN,
        Timeframe.FIVE_MIN,
        Timeframe.FIFTEEN_MIN,
        Timeframe.ONE_HOUR,
    }
)

#: Window-size guardrails. Match Dhan's documented per-request maxima.
_MAX_INTRADAY_SPAN = timedelta(days=90)
_MAX_DAILY_SPAN = timedelta(days=365 * 5)  # ≈ 5 calendar years


# ═══════════════════════════════════════════════════════════════════════
# Local typed errors
# ═══════════════════════════════════════════════════════════════════════
#
# Defined locally rather than imported from app.core.exceptions per the
# parallel-CC-session coordination rule. Future PR will consolidate to
# ``app/brokers/errors.py`` — see PATCH_INSTRUCTIONS.md.


class _DhanHistoricalError(Exception):
    """Module root error. Carries broker tag + structured metadata."""

    def __init__(
        self,
        message: str,
        *,
        broker: str = "dhan",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.broker = broker
        self.metadata: dict[str, Any] = dict(metadata) if metadata else {}

    def __str__(self) -> str:
        return f"[{self.broker}] {self.message}"


class BrokerAuthError(_DhanHistoricalError):
    """Dhan returned 401 — access token rejected.

    Treat as session-expired: route layer should emit a
    ``BROKER_DISCONNECTED`` event over the live WS and surface a
    re-link CTA in the UI. Never retry this error in-process — the
    token won't fix itself.
    """


class BrokerRateLimitError(_DhanHistoricalError):
    """429 from Dhan, OR local 5-req/sec cap exhausted after one retry.

    Carries ``retry_after`` (seconds) in ``metadata`` when Dhan provided
    a ``Retry-After`` header so the caller can decide whether to back off.
    """


class BrokerUpstreamError(_DhanHistoricalError):
    """Upstream contract failure: 5xx, non-JSON body, array-length mismatch.

    Distinct from auth / rate / param errors — circuit breaker upstream
    should react to a burst of these, but the immediate caller can
    safely surface a "broker hiccup, retrying" message.
    """


class BrokerInvalidParamsError(_DhanHistoricalError):
    """4xx-other, unsupported timeframe, range too wide, malformed input.

    These are caller bugs (or limit breaches) — retrying with the same
    params is futile.
    """


# ═══════════════════════════════════════════════════════════════════════
# DhanHistoricalClient
# ═══════════════════════════════════════════════════════════════════════


class DhanHistoricalClient:
    """Per-user historical OHLC fetcher for Dhan v2.

    The instance owns one :class:`httpx.AsyncClient` for the lifetime of
    the request and exposes :meth:`aclose` plus the async context-manager
    protocol so the route handler can use::

        async with DhanHistoricalClient(
            client_id=..., access_token=..., user_id=...
        ) as client:
            candles = await client.get_historical_ohlc(...)

    The constructor performs only argument validation — no network I/O,
    so it's safe to call from synchronous code paths if needed.
    """

    def __init__(
        self,
        *,
        client_id: str,
        access_token: str,
        user_id: UUID | str,
        base_url: str = _DHAN_BASE_URL,
    ) -> None:
        if not client_id or not client_id.strip():
            raise BrokerInvalidParamsError(
                "client_id is required (Dhan v2 sends it as the ``client-id`` header)."
            )
        if not access_token or not access_token.strip():
            raise BrokerAuthError(
                "Dhan access_token is required (per-user, never empty).",
                metadata={"client_id": client_id},
            )
        user_id_str = str(user_id).strip()
        if not user_id_str:
            raise BrokerInvalidParamsError(
                "user_id is required for per-user rate-limit keying."
            )

        self._client_id = client_id.strip()
        self._access_token = access_token.strip()
        self._user_id = user_id_str
        self._base_url = base_url
        self._http: httpx.AsyncClient | None = None
        self._log = _logger.bind(user_id=self._user_id, client_id=self._client_id)

    # ──────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────

    async def __aenter__(self) -> DhanHistoricalClient:
        await self._ensure_http()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _ensure_http(self) -> httpx.AsyncClient:
        """Lazily build the httpx pool with Dhan auth headers attached."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(
                    _HTTP_TIMEOUT_SECONDS, connect=_HTTP_CONNECT_TIMEOUT
                ),
                headers={
                    "client-id": self._client_id,
                    "access-token": self._access_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._http

    async def aclose(self) -> None:
        """Release the httpx pool. Idempotent — safe to call from finally."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    async def get_historical_ohlc(
        self,
        *,
        symbol: str,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        timeframe: Timeframe,
        from_ts: datetime,
        to_ts: datetime,
    ) -> list[Candle]:
        """Fetch OHLC bars from Dhan for ``[from_ts, to_ts]`` at ``timeframe``.

        Args:
            symbol: Trading symbol (Dhan ``tradingSymbol`` form).
                Stored on each returned :class:`Candle`.
            security_id: Dhan numeric securityId. Caller MUST resolve
                this from the scrip master — this client does not
                duplicate that cache.
            exchange_segment: Dhan exchange-segment string
                (``NSE_EQ`` / ``NSE_FNO`` / ``BSE_EQ`` / ``MCX_COMM`` / …).
            instrument: Dhan instrument category (``EQUITY``,
                ``FUTIDX``, ``OPTIDX``, ``FUTSTK``, ``OPTSTK``,
                ``INDEX``, …). Required by Dhan's payload.
            timeframe: One of the 5 supported values
                (1m / 5m / 15m / 1h / 1d). Others raise
                :class:`BrokerInvalidParamsError`.
            from_ts: Window start, must be timezone-aware.
            to_ts: Window end, must be timezone-aware, ``>= from_ts``.

        Returns:
            List of :class:`Candle`, sorted by ``timestamp`` ascending.
            Empty list when Dhan returns no bars in the window (valid —
            for symbols on holiday or new listings, the response is just
            empty arrays).

        Raises:
            BrokerInvalidParamsError: Bad/unsupported timeframe, naive
                or inverted datetimes, exceeded range guard, missing
                IDs, or Dhan returning a non-401/429/5xx 4xx.
            BrokerAuthError: Dhan 401.
            BrokerRateLimitError: Dhan 429 (after retry budget) OR
                local 5/sec cap exhausted.
            BrokerUpstreamError: Dhan 5xx / non-JSON body / structural
                response failure (array length mismatch, etc.).
        """
        self._validate_params(
            symbol=symbol,
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument=instrument,
            timeframe=timeframe,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        await self._check_local_rate_limit()

        is_intraday = timeframe in _INTRADAY_TIMEFRAMES
        path = _INTRADAY_PATH if is_intraday else _HISTORICAL_PATH

        # Dhan documents fromDate / toDate as IST local time strings.
        # Converting via astimezone() keeps the absolute instant the
        # same — only the wall-clock representation shifts.
        from_str = from_ts.astimezone(_IST).strftime("%Y-%m-%d %H:%M:%S")
        to_str = to_ts.astimezone(_IST).strftime("%Y-%m-%d %H:%M:%S")

        payload: dict[str, Any] = {
            "securityId": security_id.strip(),
            "exchangeSegment": exchange_segment.strip().upper(),
            "instrument": instrument.strip().upper(),
            "fromDate": from_str,
            "toDate": to_str,
        }
        if is_intraday:
            payload["interval"] = _TIMEFRAME_TO_DHAN[timeframe]

        self._log.info(
            "dhan_historical.request",
            symbol=symbol.upper(),
            timeframe=timeframe.value,
            path=path,
            from_ts=from_str,
            to_ts=to_str,
        )
        body = await self._request_with_retry(method="POST", path=path, payload=payload)
        return self._parse_response(symbol=symbol, timeframe=timeframe, body=body)

    # ──────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────

    def _validate_params(
        self,
        *,
        symbol: str,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        timeframe: Timeframe,
        from_ts: datetime,
        to_ts: datetime,
    ) -> None:
        """Pre-flight every caller argument. Single place for all 4xx-class checks."""
        for name, value in [
            ("symbol", symbol),
            ("security_id", security_id),
            ("exchange_segment", exchange_segment),
            ("instrument", instrument),
        ]:
            if not isinstance(value, str) or not value.strip():
                raise BrokerInvalidParamsError(
                    f"{name} must be a non-empty string.",
                    metadata={"argument": name},
                )

        if timeframe not in _TIMEFRAME_TO_DHAN:
            supported = sorted(t.value for t in _TIMEFRAME_TO_DHAN)
            raise BrokerInvalidParamsError(
                f"Timeframe {timeframe.value!r} is not supported by Dhan historical. "
                f"Supported: {supported}. Phase 2 will add downsampling for "
                "3m and 30m — see PATCH_INSTRUCTIONS.md.",
                metadata={"timeframe": timeframe.value, "supported": supported},
            )

        if from_ts.tzinfo is None or to_ts.tzinfo is None:
            raise BrokerInvalidParamsError(
                "from_ts and to_ts must be timezone-aware (UTC recommended).",
                metadata={
                    "from_tz": str(from_ts.tzinfo),
                    "to_tz": str(to_ts.tzinfo),
                },
            )
        if from_ts > to_ts:
            raise BrokerInvalidParamsError(
                f"from_ts ({from_ts.isoformat()}) must be <= to_ts ({to_ts.isoformat()}).",
                metadata={"from_ts": from_ts.isoformat(), "to_ts": to_ts.isoformat()},
            )

        span = to_ts - from_ts
        if timeframe == Timeframe.ONE_DAY:
            if span > _MAX_DAILY_SPAN:
                raise BrokerInvalidParamsError(
                    f"Daily timeframe max range is {_MAX_DAILY_SPAN.days} days; "
                    f"got {span.days} days. Chunking is a Phase 2 enhancement — "
                    "see PATCH_INSTRUCTIONS.md.",
                    metadata={"span_days": span.days, "max_days": _MAX_DAILY_SPAN.days},
                )
        else:
            if span > _MAX_INTRADAY_SPAN:
                raise BrokerInvalidParamsError(
                    f"Intraday timeframe max range is {_MAX_INTRADAY_SPAN.days} days; "
                    f"got {span.days} days. Chunking is a Phase 2 enhancement — "
                    "see PATCH_INSTRUCTIONS.md.",
                    metadata={
                        "span_days": span.days,
                        "max_days": _MAX_INTRADAY_SPAN.days,
                    },
                )

    # ──────────────────────────────────────────────────────────────────
    # Rate limiting
    # ──────────────────────────────────────────────────────────────────

    async def _check_local_rate_limit(self) -> None:
        """Per-user 5/sec preflight via the shared Redis fixed-window counter.

        Key shape: ``rate:dhan_historical:{user_id}`` (the ``rate:``
        prefix is added by :func:`rate_limit_check` internally).

        Behaviour:
            * First check passes → return immediately.
            * Fails → sleep ``_LOCAL_RATE_RETRY_SLEEP_S`` (covers a
              fixed-window rollover) → check once more.
            * Still failing → raise :class:`BrokerRateLimitError`.

        No infinite retry — the caller (a sync HTTP request) cannot
        afford to block longer than its own client timeout.
        """
        key = f"dhan_historical:{self._user_id}"
        allowed = await rate_limit_check(
            key,
            max_requests=_LOCAL_RATE_MAX,
            window_seconds=_LOCAL_RATE_WINDOW_S,
        )
        if allowed:
            return

        self._log.info(
            "dhan_historical.local_rate_limit_hit",
            user_id=self._user_id,
            backoff_seconds=_LOCAL_RATE_RETRY_SLEEP_S,
        )
        await asyncio.sleep(_LOCAL_RATE_RETRY_SLEEP_S)
        retried = await rate_limit_check(
            key,
            max_requests=_LOCAL_RATE_MAX,
            window_seconds=_LOCAL_RATE_WINDOW_S,
        )
        if retried:
            return

        raise BrokerRateLimitError(
            "Dhan historical local rate limit (5 req/sec per user) exhausted "
            "after one retry. Backoff aur try kar — short window mein bahut "
            "requests aa rahe hain.",
            metadata={"user_id": self._user_id, "key": f"rate:{key}"},
        )

    # ──────────────────────────────────────────────────────────────────
    # HTTP request + reactive retry
    # ──────────────────────────────────────────────────────────────────

    async def _request_with_retry(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Issue one Dhan request with 429/5xx exponential-backoff retries.

        Returns the parsed JSON body on the first 2xx response. Maps
        every other status onto the local typed error hierarchy. Network
        errors (timeout, DNS, TCP) count as transient and burn the
        retry budget.
        """
        http = await self._ensure_http()
        last_status: int | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await http.request(method, path, json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                self._log.warning(
                    "dhan_historical.network_error",
                    attempt=attempt,
                    path=path,
                    error=type(exc).__name__,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_backoff_delay(attempt))
                    continue
                raise BrokerUpstreamError(
                    f"Dhan historical network failure after {attempt} attempts.",
                    metadata={"path": path, "attempts": attempt},
                ) from exc
            except httpx.HTTPError as exc:
                # Catch-all for any other httpx exception (e.g. invalid URL).
                raise BrokerUpstreamError(
                    f"Dhan historical HTTP error: {type(exc).__name__}",
                    metadata={"path": path, "attempts": attempt},
                ) from exc

            status = response.status_code
            last_status = status

            if status == 401:
                raise BrokerAuthError(
                    "Dhan access token rejected (401). Session expired ho gayi — "
                    "broker reconnect karna padega.",
                    metadata={"path": path, "user_id": self._user_id},
                )

            if status == 429:
                retry_after_hdr = response.headers.get("Retry-After")
                try:
                    retry_after = float(retry_after_hdr) if retry_after_hdr else None
                except (TypeError, ValueError):
                    retry_after = None
                if attempt < _MAX_RETRIES:
                    delay = retry_after if retry_after is not None else _backoff_delay(attempt)
                    self._log.warning(
                        "dhan_historical.rate_limited_upstream",
                        attempt=attempt,
                        retry_after=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise BrokerRateLimitError(
                    "Dhan upstream rate limit (429) — retry budget exhausted.",
                    metadata={
                        "path": path,
                        "attempts": attempt,
                        "retry_after": retry_after,
                    },
                )

            if 500 <= status < 600:
                if attempt < _MAX_RETRIES:
                    self._log.warning(
                        "dhan_historical.upstream_5xx",
                        attempt=attempt,
                        status=status,
                    )
                    await asyncio.sleep(_backoff_delay(attempt))
                    continue
                raise BrokerUpstreamError(
                    f"Dhan historical {status} after {attempt} attempts.",
                    metadata={"path": path, "status": status, "attempts": attempt},
                )

            if 400 <= status < 500:
                try:
                    err_body: Any = response.json()
                except ValueError:
                    err_body = {}
                if not isinstance(err_body, dict):
                    err_body = {"raw": err_body}
                message = str(
                    err_body.get("errorMessage")
                    or err_body.get("message")
                    or f"Dhan {status}"
                )
                raise BrokerInvalidParamsError(
                    message,
                    metadata={"path": path, "status": status, "raw": err_body},
                )

            try:
                body = response.json()
            except ValueError as exc:
                raise BrokerUpstreamError(
                    "Dhan historical returned non-JSON body.",
                    metadata={"path": path, "status": status},
                ) from exc
            if not isinstance(body, dict):
                raise BrokerUpstreamError(
                    "Dhan historical response was not a JSON object.",
                    metadata={"path": path, "type": type(body).__name__},
                )
            return body

        # ``range(1, _MAX_RETRIES + 1)`` always returns or continues — falling
        # out of the loop is structurally unreachable, but mypy can't see
        # that and we want a defensible error if it ever happens.
        raise BrokerUpstreamError(  # pragma: no cover
            "Dhan historical retry loop exited unexpectedly.",
            metadata={"path": path, "last_status": last_status},
        )

    # ──────────────────────────────────────────────────────────────────
    # Response parsing
    # ──────────────────────────────────────────────────────────────────

    def _parse_response(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        body: dict[str, Any],
    ) -> list[Candle]:
        """Translate Dhan's column-oriented payload into a list of Candles.

        Dhan returns each OHLC column as a parallel array:

            {"open": [...], "high": [...], "low": [...], "close": [...],
             "volume": [...], "timestamp": [<epoch_seconds>, ...]}

        Some Dhan tenants wrap this under ``"data"``; we unwrap if present.

        * Empty arrays are a valid response (no trades in window) — returns ``[]``.
        * Array length mismatch among required columns → BrokerUpstreamError
          (structural integrity failure — the upstream contract is broken).
        * Per-row decode failures (bad timestamps, invalid OHLC numbers, Pydantic
          validator rejections) are logged and skipped so a partial broker
          response still renders most of the chart.
        * If we end up parsing N>0 rows and ALL of them fail decode →
          BrokerUpstreamError (every row malformed = upstream is broken).
        """
        data = body.get("data") if isinstance(body.get("data"), dict) else body

        opens = data.get("open") or []
        highs = data.get("high") or []
        lows = data.get("low") or []
        closes = data.get("close") or []
        volumes = data.get("volume") or []
        # ``start_Time`` is a Dhan tenant variant we've seen in sandbox.
        timestamps = data.get("timestamp") or data.get("start_Time") or []

        for name, arr in (
            ("open", opens),
            ("high", highs),
            ("low", lows),
            ("close", closes),
            ("timestamp", timestamps),
        ):
            if not isinstance(arr, list):
                raise BrokerUpstreamError(
                    f"Dhan historical field {name!r} was not an array.",
                    metadata={"field": name, "type": type(arr).__name__},
                )
        if not isinstance(volumes, list):
            raise BrokerUpstreamError(
                "Dhan historical field 'volume' was not an array.",
                metadata={"field": "volume", "type": type(volumes).__name__},
            )

        if not timestamps:
            self._log.info(
                "dhan_historical.empty_window",
                symbol=symbol.upper(),
                timeframe=timeframe.value,
            )
            return []

        n = len(timestamps)
        for name, arr in (
            ("open", opens),
            ("high", highs),
            ("low", lows),
            ("close", closes),
        ):
            if len(arr) != n:
                raise BrokerUpstreamError(
                    f"Dhan historical array-length mismatch: timestamp={n} "
                    f"vs {name}={len(arr)}.",
                    metadata={"field": name, "expected": n, "actual": len(arr)},
                )
        if volumes and len(volumes) != n:
            raise BrokerUpstreamError(
                f"Dhan historical 'volume' length mismatch: timestamp={n} "
                f"vs volume={len(volumes)}.",
                metadata={"field": "volume", "expected": n, "actual": len(volumes)},
            )

        upper = symbol.strip().upper()
        bars: list[Candle] = []
        # Collect dropped-row diagnostics for one structured summary log
        # at the end of the parse — avoids per-row log spam on a bad
        # upstream payload (10k bars × one warn each = noisy).
        dropped_indices: list[int] = []
        dropped_errors: list[str] = []
        for i in range(n):
            try:
                ts_raw = timestamps[i]
                if isinstance(ts_raw, datetime):
                    ts = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=UTC)
                else:
                    # Epoch seconds are tz-independent absolutes; UTC tag.
                    ts = datetime.fromtimestamp(int(ts_raw), tz=UTC)
                vol = int(volumes[i] or 0) if volumes else 0
                bars.append(
                    Candle(
                        symbol=upper,
                        timeframe=timeframe,
                        timestamp=ts,
                        open=_money(opens[i]),
                        high=_money(highs[i]),
                        low=_money(lows[i]),
                        close=_money(closes[i]),
                        volume=vol,
                    )
                )
            except (
                TypeError,
                ValueError,
                ArithmeticError,
                InvalidOperation,
                ValidationError,
            ) as exc:
                dropped_indices.append(i)
                # Cap stored error strings so a 10k-row blowout doesn't
                # balloon the log line; first 10 are enough to diagnose.
                if len(dropped_errors) < 10:
                    dropped_errors.append(f"row[{i}]: {type(exc).__name__}: {exc}")

        if not bars and n > 0:
            raise BrokerUpstreamError(
                f"Dhan historical: all {n} rows failed decode — upstream payload broken.",
                metadata={
                    "symbol": upper,
                    "timeframe": timeframe.value,
                    "rows": n,
                    "sample_errors": dropped_errors,
                },
            )

        if dropped_indices:
            # Structured log for prod debugging. ``user_id`` is bound on
            # ``self._log`` at construction; ``request_id`` flows in via
            # structlog contextvars (bound by the route handler via
            # ``app.core.logging.bind_request_context``) — both appear
            # automatically in every JSON log line emitted here.
            self._log.warning(
                "dhan_historical.rows_dropped",
                symbol=upper,
                timeframe=timeframe.value,
                dropped_count=len(dropped_indices),
                total_count=n,
                kept_count=len(bars),
                dropped_indices=dropped_indices[:20],
                sample_errors=dropped_errors,
            )

        bars.sort(key=lambda c: c.timestamp)
        return bars


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════


def _money(value: Any) -> Decimal:
    """Loss-free coercion of a price field to :class:`Decimal`.

    Refuses ``None`` and the empty string — both indicate an incomplete
    bar from Dhan, which the caller's exception handler turns into a
    dropped row. We deliberately go via ``str()`` so floats like
    ``42.1`` don't round-trip through binary representation.
    """
    if value is None:
        raise ValueError("price value cannot be None")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str) and not value.strip():
        raise ValueError("price value cannot be empty string")
    return Decimal(str(value))


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with ±25% jitter, capped at ``_RETRY_MAX_DELAY_S``.

    Attempt 1 → ~0.5s + jitter
    Attempt 2 → ~1.0s + jitter
    Attempt 3 → ~2.0s + jitter (caps at 4s)
    """
    base = min(_RETRY_BASE_DELAY_S * (2 ** (attempt - 1)), _RETRY_MAX_DELAY_S)
    jitter = random.uniform(0, base * 0.25)
    return base + jitter


__all__ = [
    "BrokerAuthError",
    "BrokerInvalidParamsError",
    "BrokerRateLimitError",
    "BrokerUpstreamError",
    "DhanHistoricalClient",
]
