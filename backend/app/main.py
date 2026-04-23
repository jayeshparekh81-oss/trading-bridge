"""FastAPI application entrypoint.

* Lifespan owns the external connections (DB engine, Redis client) so
  requests never trigger lazy cold-start work.
* Placeholder routers reserve the URL prefixes; concrete handlers land
  in later steps.
* Exception handlers translate our ``BrokerError`` hierarchy into
  structured JSON — never let a 500 leak the raw traceback.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerError,
    BrokerInsufficientFundsError,
    BrokerInvalidSymbolError,
    BrokerOrderRejectedError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
)
from app.core.logging import configure_logging, get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis

from app.api.docs import (
    APP_DESCRIPTION,
    APP_TITLE,
    APP_VERSION,
    CONTACT,
    LICENSE_INFO,
    TAGS_METADATA,
)

logger = get_logger("app.main")


# ═══════════════════════════════════════════════════════════════════════
# Lifespan — DB + Redis connection management
# ═══════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open DB engine + Redis client on startup, close on shutdown."""
    configure_logging()
    settings = get_settings()

    # Local imports keep cold-start cost off the module-import path —
    # also lets tests mock these symbols without re-importing app.main.
    import redis.asyncio as aioredis

    from app.db.session import dispose_engine, get_engine

    app.state.db_engine = get_engine()
    app.state.redis = aioredis.from_url(
        settings.redis_url, encoding="utf-8", decode_responses=True
    )
    logger.info("app.startup", environment=settings.environment.value)

    try:
        yield
    finally:
        redis_client: aioredis.Redis | None = getattr(app.state, "redis", None)
        if redis_client is not None:
            await redis_client.aclose()
        await dispose_engine()
        logger.info("app.shutdown")


# ═══════════════════════════════════════════════════════════════════════
# App factory
# ═══════════════════════════════════════════════════════════════════════


def _register_exception_handlers(app: FastAPI) -> None:
    """Map every ``BrokerError`` subclass to a structured JSON response."""

    _422 = getattr(
        status,
        "HTTP_422_UNPROCESSABLE_CONTENT",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )
    status_by_exc: dict[type[BrokerError], int] = {
        BrokerAuthError: status.HTTP_401_UNAUTHORIZED,
        BrokerSessionExpiredError: status.HTTP_401_UNAUTHORIZED,
        BrokerOrderRejectedError: _422,
        BrokerInvalidSymbolError: _422,
        BrokerInsufficientFundsError: _422,
        BrokerRateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
        BrokerConnectionError: status.HTTP_502_BAD_GATEWAY,
    }

    async def broker_error_handler(request: Request, exc: BrokerError) -> JSONResponse:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        for exc_cls, code in status_by_exc.items():
            if isinstance(exc, exc_cls):
                http_status = code
                break

        body: dict[str, Any] = {
            "error": type(exc).__name__,
            "broker": exc.broker_name,
            "message": exc.message,
            "metadata": exc.metadata,
        }
        if isinstance(exc, BrokerOrderRejectedError):
            body["reason"] = exc.reason
        if isinstance(exc, BrokerRateLimitError) and exc.retry_after is not None:
            body["retry_after"] = exc.retry_after

        logger.warning(
            "broker_error",
            path=request.url.path,
            error=type(exc).__name__,
            broker=exc.broker_name,
        )
        return JSONResponse(status_code=http_status, content=body)

    app.add_exception_handler(BrokerError, broker_error_handler)  # type: ignore[arg-type]


def _register_routers(app: FastAPI) -> None:
    """Mount all routers."""
    from app.api.admin import router as admin_router
    from app.api.brokers import router as brokers_router
    from app.api.auth import router as auth_router
    from app.api.health import router as health_router
    from app.api.kill_switch import router as kill_switch_router
    from app.api.users import router as users_router
    from app.api.webhook import router as webhook_router

    app.include_router(webhook_router)
    app.include_router(health_router)
    app.include_router(kill_switch_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(admin_router)
    app.include_router(brokers_router)


def _register_middleware(app: FastAPI) -> None:
    """Attach ASGI middleware in the correct order.

    ``add_middleware`` pushes onto a stack, so the LAST-added middleware
    is the OUTERMOST. We register from inner-to-outer so the final chain
    reads: security-headers (outermost) → sensitive-filter → timing →
    trusted-proxy → size-limit → request-id (innermost) → CORS → app.
    """
    from app.middleware.security import (
        RequestIDMiddleware,
        RequestSizeLimitMiddleware,
        ResponseTimingMiddleware,
        SecurityHeadersMiddleware,
        SensitiveDataFilterMiddleware,
        TrustedProxyMiddleware,
    )

    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        RequestSizeLimitMiddleware, max_bytes=settings.max_request_body_size
    )
    app.add_middleware(
        TrustedProxyMiddleware,
        trusted_proxies=settings.trusted_proxy_ips,
    )
    app.add_middleware(ResponseTimingMiddleware)
    app.add_middleware(SensitiveDataFilterMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)


def create_app() -> FastAPI:
    """Build and return a configured :class:`FastAPI` instance."""
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=TAGS_METADATA,
        contact=CONTACT,
        license_info=LICENSE_INFO,
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_routers(app)
    _register_exception_handlers(app)

    return app


app = create_app()


__all__ = ["app", "create_app", "lifespan"]
