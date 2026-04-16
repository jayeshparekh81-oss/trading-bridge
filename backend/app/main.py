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

from fastapi import APIRouter, FastAPI, Request, status
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

APP_TITLE = "Trading Bridge API"
APP_VERSION = "0.1.0"

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
    """Mount placeholder routers — concrete handlers arrive in later steps."""
    for prefix, tag in (
        ("/api/webhook", "webhook"),
        ("/api/auth", "auth"),
        ("/api/users", "users"),
        ("/api/admin", "admin"),
    ):
        router = APIRouter(prefix=prefix, tags=[tag])
        app.include_router(router)


def create_app() -> FastAPI:
    """Build and return a configured :class:`FastAPI` instance."""
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_routers(app)
    _register_exception_handlers(app)

    @app.get("/health", tags=["health"])
    async def health(request: Request) -> dict[str, Any]:
        """Liveness + readiness probe.

        Runs a cheap round-trip against Postgres and Redis — both must
        respond for the pod to be considered ready.
        """
        from sqlalchemy import text

        db_ok = False
        redis_ok = False

        engine = getattr(request.app.state, "db_engine", None)
        if engine is not None:
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                db_ok = True
            except Exception as exc:  # noqa: BLE001 — never 500 the probe
                logger.warning("health.db_failed", error=str(exc))

        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is not None:
            try:
                pong = await redis_client.ping()
                redis_ok = bool(pong)
            except Exception as exc:  # noqa: BLE001
                logger.warning("health.redis_failed", error=str(exc))

        status_label = "ok" if db_ok and redis_ok else "degraded"
        return {"status": status_label, "db": db_ok, "redis": redis_ok}

    return app


app = create_app()


__all__ = ["app", "create_app", "lifespan"]
