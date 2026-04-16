"""Security-focused ASGI middleware.

Each class is standalone so ``create_app`` can pick and compose them.
Every middleware here is stateless aside from module-level config — all
per-request state is pushed into ``request.state`` or response headers.
"""

from __future__ import annotations

import ipaddress
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import ClassVar, Iterable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import bind_request_context, clear_request_context, get_logger

logger = get_logger("app.middleware")


# ═══════════════════════════════════════════════════════════════════════
# Security headers
# ═══════════════════════════════════════════════════════════════════════


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP baseline response headers.

    The header set is static — CSP is intentionally strict (``self``
    only). Endpoints that legitimately need relaxed CSP (e.g. Swagger
    UI) are explicitly allowed via ``swagger_paths``.
    """

    DEFAULT_HEADERS: ClassVar[dict[str, str]] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": (
            "max-age=31536000; includeSubDomains; preload"
        ),
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "camera=(), microphone=(), geolocation=(), payment=()"
        ),
        "X-Permitted-Cross-Domain-Policies": "none",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }

    #: Paths that host HTML assets (Swagger) — CSP loosened for them.
    _DOC_PATHS: ClassVar[tuple[str, ...]] = ("/docs", "/redoc", "/openapi.json")

    def __init__(self, app: ASGIApp, *, extra: dict[str, str] | None = None) -> None:
        super().__init__(app)
        self._extra = dict(extra or {})

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        for key, value in self.DEFAULT_HEADERS.items():
            if key == "Content-Security-Policy" and path.startswith(self._DOC_PATHS):
                continue
            response.headers.setdefault(key, value)
        for key, value in self._extra.items():
            response.headers[key] = value
        return response


# ═══════════════════════════════════════════════════════════════════════
# Request ID
# ═══════════════════════════════════════════════════════════════════════


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Stamp every request with a UUID4 ``request_id``.

    Honours ``X-Request-ID`` from upstream load balancers when present
    (helps trace a request across edge → API). Otherwise generates fresh.
    """

    HEADER = "X-Request-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(self.HEADER)
        request_id = incoming if _is_plausible_request_id(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        bind_request_context(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context("request_id")
        response.headers[self.HEADER] = request_id
        return response


def _is_plausible_request_id(value: str | None) -> bool:
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9\-]{8,128}", value))


# ═══════════════════════════════════════════════════════════════════════
# Response timing
# ═══════════════════════════════════════════════════════════════════════


class ResponseTimingMiddleware(BaseHTTPMiddleware):
    """Emit ``X-Process-Time`` (ms) on every response."""

    HEADER = "X-Process-Time"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[self.HEADER] = f"{elapsed_ms:.3f}"
        return response


# ═══════════════════════════════════════════════════════════════════════
# Trusted proxy (extract real client IP)
# ═══════════════════════════════════════════════════════════════════════


class TrustedProxyMiddleware(BaseHTTPMiddleware):
    """Resolve ``request.state.client_ip`` from ``X-Forwarded-For``.

    Only honours the forwarded header when the immediate peer is in the
    configured trusted-proxy list — otherwise an attacker could spoof
    their source IP by adding the header themselves.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        trusted_proxies: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._nets = _parse_networks(trusted_proxies or ())

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.client_ip = self._resolve(request)
        return await call_next(request)

    def _resolve(self, request: Request) -> str | None:
        peer = request.client.host if request.client else None
        if peer and self._is_trusted(peer):
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return peer

    def _is_trusted(self, ip: str) -> bool:
        try:
            parsed = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(parsed in net for net in self._nets)


def _parse_networks(
    values: Iterable[str],
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for v in values:
        try:
            nets.append(ipaddress.ip_network(v, strict=False))
        except ValueError:
            logger.warning("middleware.bad_trusted_proxy", value=v)
    return tuple(nets)


# ═══════════════════════════════════════════════════════════════════════
# Request size limit
# ═══════════════════════════════════════════════════════════════════════


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject bodies larger than ``max_bytes`` (DoS prevention)."""

    def __init__(self, app: ASGIApp, *, max_bytes: int = 1_048_576) -> None:
        super().__init__(app)
        self._max = max_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "invalid Content-Length"},
                )
            if declared > self._max:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "detail": f"request body exceeds {self._max} bytes",
                    },
                )
        return await call_next(request)


# ═══════════════════════════════════════════════════════════════════════
# Sensitive-data filter (error response scrubbing)
# ═══════════════════════════════════════════════════════════════════════


class SensitiveDataFilterMiddleware(BaseHTTPMiddleware):
    """Replace stack-trace / internal detail on 5xx JSON responses.

    FastAPI already hides tracebacks with ``debug=False``, but if a
    downstream handler ever leaks internals, this is the last-mile guard.
    Any 5xx response with a JSON body is replaced with a generic
    ``{"detail": "internal error", "request_id": "..."}`` payload.
    """

    _SAFE_STATUS: ClassVar[frozenset[int]] = frozenset(range(100, 500))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if response.status_code in self._SAFE_STATUS:
            return response
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response
        # Drain the upstream body so we don't leak a streamed payload even
        # when we replace the response. BaseHTTPMiddleware wraps handler
        # output in a streaming response, so a plain isinstance check on
        # JSONResponse doesn't match here — rely on the content-type gate.
        body_iter = getattr(response, "body_iterator", None)
        if body_iter is not None:
            async for _ in body_iter:
                pass
        safe_headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-length", "content-type")
        }
        return JSONResponse(
            status_code=response.status_code,
            content={
                "detail": "internal error",
                "request_id": getattr(request.state, "request_id", None),
            },
            headers=safe_headers,
        )


__all__ = [
    "RequestIDMiddleware",
    "RequestSizeLimitMiddleware",
    "ResponseTimingMiddleware",
    "SecurityHeadersMiddleware",
    "SensitiveDataFilterMiddleware",
    "TrustedProxyMiddleware",
]
