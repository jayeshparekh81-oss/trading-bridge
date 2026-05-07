"""Pure HTTP layer for Dhan historical-data calls.

Tiny wrapper around :mod:`httpx` that:

    * Picks the daily / intraday URL from the requested timeframe.
    * Builds the body Dhan expects (``securityId`` plus enums plus
      date-range strings in the format the relevant endpoint requires).
    * Retries up to :data:`MAX_RETRY_ATTEMPTS` times on ``429`` or 5xx,
      using ``Retry-After`` when present otherwise an exponential
      schedule starting at :data:`INITIAL_BACKOFF_SECONDS`.
    * Parses the columnar response into a list of :class:`Candle`
      objects.

Tests inject the HTTP layer via the ``http_post`` and ``sleep_fn``
parameters on :func:`fetch_from_dhan` so no real network or wall-clock
time is consumed in the test suite.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.strategy_engine.data_provider.constants import (
    DAILY_TIMEFRAME,
    DHAN_API_BASE_URL,
    DHAN_HISTORICAL_DAILY_PATH,
    DHAN_HISTORICAL_INTRADAY_PATH,
    INITIAL_BACKOFF_SECONDS,
    MAX_RETRY_ATTEMPTS,
    TIMEFRAME_TO_INTERVAL_MINUTES,
)
from app.strategy_engine.data_provider.models import (
    DhanFetchError,
    HistoricalDataRequest,
)
from app.strategy_engine.schema.ohlcv import Candle

HttpPost = Callable[..., httpx.Response]
SleepFn = Callable[[float], None]


def fetch_from_dhan(
    request: HistoricalDataRequest,
    *,
    access_token: str,
    security_id: str,
    exchange_segment: str,
    instrument: str,
    base_url: str = DHAN_API_BASE_URL,
    http_post: HttpPost = httpx.post,
    sleep_fn: SleepFn = time.sleep,
) -> dict[str, Any]:
    """Issue the Dhan historical-data POST and return the parsed JSON
    body.

    The seven keyword-only parameters below the request let tests
    inject mocks without touching module globals or patching httpx:
    pass an ``http_post`` that returns a synthetic
    :class:`httpx.Response` and a ``sleep_fn`` that records calls
    instead of blocking.

    Raises:
        :class:`DhanFetchError`: when retries are exhausted or the
            response is not parseable. The exception carries the
            final status code + Dhan error code when available.
    """
    url = base_url.rstrip("/") + _path_for_timeframe(request.timeframe)
    headers = {
        "access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = _build_body(
        request,
        security_id=security_id,
        exchange_segment=exchange_segment,
        instrument=instrument,
    )

    last_error: BaseException | None = None
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            response = http_post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            last_error = exc
            _backoff(attempt, sleep_fn=sleep_fn)
            continue

        if 200 <= response.status_code < 300:
            return _parse_json(response)

        if response.status_code == 429 or 500 <= response.status_code < 600:
            retry_after = _retry_after(response)
            if attempt + 1 == MAX_RETRY_ATTEMPTS:
                last_error = DhanFetchError(
                    f"Dhan historical fetch exhausted retries (last status "
                    f"{response.status_code}).",
                    status_code=response.status_code,
                )
                break
            _wait(retry_after, attempt, sleep_fn=sleep_fn)
            continue

        # Non-retryable status — surface the error body and stop.
        raise DhanFetchError(
            _error_message_from(response),
            status_code=response.status_code,
            error_code=_error_code_from(response),
        )

    if isinstance(last_error, DhanFetchError):
        raise last_error
    raise DhanFetchError(
        "Dhan historical fetch failed after retries.",
        original_error=last_error,
    )


# ─── Body / URL builders ──────────────────────────────────────────────


def _path_for_timeframe(timeframe: str) -> str:
    if timeframe == DAILY_TIMEFRAME:
        return DHAN_HISTORICAL_DAILY_PATH
    return DHAN_HISTORICAL_INTRADAY_PATH


def _build_body(
    request: HistoricalDataRequest,
    *,
    security_id: str,
    exchange_segment: str,
    instrument: str,
) -> dict[str, Any]:
    """Assemble the Dhan request body. Daily and intraday share most
    fields; intraday adds ``interval`` + uses datetime granularity for
    ``fromDate`` / ``toDate``."""
    if request.timeframe == DAILY_TIMEFRAME:
        return {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "fromDate": request.from_date.strftime("%Y-%m-%d"),
            "toDate": request.to_date.strftime("%Y-%m-%d"),
        }
    return {
        "securityId": security_id,
        "exchangeSegment": exchange_segment,
        "instrument": instrument,
        "interval": TIMEFRAME_TO_INTERVAL_MINUTES[request.timeframe],
        "fromDate": request.from_date.strftime("%Y-%m-%d %H:%M:%S"),
        "toDate": request.to_date.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─── Response parsing ─────────────────────────────────────────────────


def parse_candles(payload: dict[str, Any]) -> list[Candle]:
    """Convert the Dhan columnar response into ``Candle`` objects.

    Dhan returns parallel arrays of ``open``, ``high``, ``low``,
    ``close``, ``volume``, ``timestamp`` (and optionally
    ``open_interest``). Phase B normalises them into the Phase 1
    :class:`Candle` shape, dropping ``open_interest`` (the Candle
    model doesn't carry it).

    Raises:
        :class:`DhanFetchError`: when arrays are missing, mismatched,
            or contain values that fail Candle validation.
    """
    try:
        opens = list(payload["open"])
        highs = list(payload["high"])
        lows = list(payload["low"])
        closes = list(payload["close"])
        volumes = list(payload["volume"])
        timestamps = list(payload["timestamp"])
    except KeyError as exc:
        raise DhanFetchError(f"Dhan response missing required column: {exc.args[0]!r}") from exc

    n = len(timestamps)
    if not (len(opens) == len(highs) == len(lows) == len(closes) == len(volumes) == n):
        raise DhanFetchError(
            "Dhan response columns have inconsistent lengths "
            f"(timestamp={n}, open={len(opens)}, high={len(highs)}, "
            f"low={len(lows)}, close={len(closes)}, volume={len(volumes)})."
        )

    candles: list[Candle] = []
    for i in range(n):
        ts = datetime.fromtimestamp(int(timestamps[i]), tz=UTC)
        try:
            candles.append(
                Candle(
                    timestamp=ts,
                    open=float(opens[i]),
                    high=float(highs[i]),
                    low=float(lows[i]),
                    close=float(closes[i]),
                    volume=float(volumes[i]),
                )
            )
        except (ValueError, TypeError) as exc:
            raise DhanFetchError(f"Dhan response row {i} failed Candle validation: {exc}") from exc
    return candles


# ─── Retry helpers ────────────────────────────────────────────────────


def _retry_after(response: httpx.Response) -> float | None:
    """Parse ``Retry-After`` (seconds) from the response, if present."""
    raw = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _wait(retry_after: float | None, attempt: int, *, sleep_fn: SleepFn) -> None:
    """Sleep for ``retry_after`` if present, otherwise exponential."""
    if retry_after is not None and retry_after > 0:
        sleep_fn(retry_after)
        return
    sleep_fn(INITIAL_BACKOFF_SECONDS * (2**attempt))


def _backoff(attempt: int, *, sleep_fn: SleepFn) -> None:
    """Same exponential schedule as ``_wait`` without the
    ``Retry-After`` short-circuit. Used after a network exception."""
    sleep_fn(INITIAL_BACKOFF_SECONDS * (2**attempt))


def _parse_json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise DhanFetchError(
            f"Dhan returned non-JSON body (status {response.status_code}).",
            status_code=response.status_code,
            original_error=exc,
        ) from exc
    if not isinstance(body, dict):
        raise DhanFetchError(
            f"Dhan returned non-object JSON: {type(body).__name__}.",
            status_code=response.status_code,
        )
    return body


def _error_message_from(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"Dhan returned status {response.status_code} with non-JSON body."
    if isinstance(body, dict):
        return str(body.get("errorMessage") or body.get("message") or body)
    return str(body)


def _error_code_from(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        code = body.get("errorCode") or body.get("error_code")
        return str(code) if code is not None else None
    return None


__all__ = [
    "fetch_from_dhan",
    "parse_candles",
]
