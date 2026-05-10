"""Slow-request structured logger.

A FastAPI middleware that emits one structured ``request.slow`` log
line per request whose total wall-clock duration exceeds a
configurable threshold (default 500 ms). Fast requests pay only the
``time.perf_counter`` calls and a single comparison — no log emission,
no hashing, no allocation beyond the timer.

Why a separate middleware (we already have ``ResponseTimingMiddleware``):

    * ``ResponseTimingMiddleware`` adds the ``X-Process-Time`` header
      so clients + Sentry can attribute latency. It does **not**
      structured-log per request, by design — emitting a log line for
      every request would dominate log volume and cost.
    * This middleware logs only the slow tail. The threshold is
      readable + adjustable via env so we can dial it down during
      hot-investigation windows without a deploy.

User-id privacy: the logged ``user_id_hash`` is the
``hash_user_id`` salted SHA-256 — never the raw UUID. We read the
attached user from ``request.state.user`` if present (the auth
dependency populates it) and elide the field otherwise.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger
from app.observability.pii_scrubber import hash_user_id

logger = get_logger("app.observability.perf_logger")

#: Default slow-request threshold in milliseconds. Override via the
#: ``PERF_SLOW_REQUEST_MS`` env var at process start.
DEFAULT_THRESHOLD_MS = 500.0


def _resolve_threshold() -> float:
    raw = os.environ.get("PERF_SLOW_REQUEST_MS")
    if not raw:
        return DEFAULT_THRESHOLD_MS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_THRESHOLD_MS
    # Negative / zero would log every request; clamp to 1 ms.
    return max(value, 1.0)


def _safe_user_id(request: Request) -> str | None:
    """Pull a user id off the request without raising.

    ``request.state.user`` is set by the auth dependency for any
    authenticated request — but unauthenticated public routes won't
    have it, so we return ``None`` quietly instead of failing the
    log.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    user_id = getattr(user, "id", None)
    if user_id is None:
        return None
    return str(user_id)


class SlowRequestLoggerMiddleware(BaseHTTPMiddleware):
    """Emit ``request.slow`` for any request slower than the threshold.

    The middleware never raises; if the downstream handler raises, the
    exception still propagates but we log a ``request.slow_failed``
    line with the duration so tail-latency attribution survives even
    when the response itself does not.
    """

    def __init__(
        self, app: Any, *, threshold_ms: float | None = None
    ) -> None:
        super().__init__(app)
        # Allow tests to inject a low threshold without touching env;
        # production defaults read from env at process start.
        self._threshold_ms: float = (
            threshold_ms if threshold_ms is not None else _resolve_threshold()
        )

    @property
    def threshold_ms(self) -> float:
        return self._threshold_ms

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if elapsed_ms >= self._threshold_ms:
                logger.warning(
                    "request.slow_failed",
                    path=request.url.path,
                    method=request.method,
                    duration_ms=round(elapsed_ms, 2),
                    user_id_hash=_hashed_user_or_none(request),
                    request_id=_request_id_or_none(request),
                )
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= self._threshold_ms:
            logger.warning(
                "request.slow",
                path=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=round(elapsed_ms, 2),
                threshold_ms=self._threshold_ms,
                user_id_hash=_hashed_user_or_none(request),
                request_id=_request_id_or_none(request),
            )
        return response


def _hashed_user_or_none(request: Request) -> str | None:
    raw = _safe_user_id(request)
    if raw is None:
        return None
    return hash_user_id(raw)


def _request_id_or_none(request: Request) -> str | None:
    """Pull the request id set by ``RequestIDMiddleware`` (if any)."""
    rid = getattr(request.state, "request_id", None)
    if rid is None:
        return None
    if isinstance(rid, uuid.UUID):
        return str(rid)
    return str(rid) if isinstance(rid, str) else None


__all__ = [
    "DEFAULT_THRESHOLD_MS",
    "SlowRequestLoggerMiddleware",
]
