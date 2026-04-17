"""Startup validation — fail fast with clear error messages.

Called from the FastAPI lifespan on boot. If ANY check fails, the process
logs a CRITICAL message and exits with code 1. This prevents a half-broken
instance from serving traffic and confusing operators with cryptic 500s.
"""

from __future__ import annotations

import platform
from typing import Any

import fastapi

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.core.startup")

_BANNER = r"""
╔═══════════════════════════════════════════════════════╗
║              TRADING BRIDGE v1.0.0                    ║
║     India's Fastest Algo Trading Bridge               ║
╚═══════════════════════════════════════════════════════╝
"""


class StartupCheckError(RuntimeError):
    """Raised when a startup check fails."""


async def run_startup_checks() -> dict[str, Any]:
    """Validate that the runtime environment is correctly configured.

    Returns a dict of system info on success. Raises :class:`StartupCheckError`
    on the first failure.
    """
    settings = get_settings()
    results: dict[str, str] = {}

    # 1. Encryption key
    _check_encryption_key(settings)
    results["encryption_key"] = "ok"

    # 2. JWT secret
    _check_jwt_secret(settings)
    results["jwt_secret"] = "ok"

    # 3. Database connectivity
    await _check_database(settings)
    results["database"] = "ok"

    # 4. Redis connectivity
    await _check_redis(settings)
    results["redis"] = "ok"

    # 5. System info
    info = _system_info(settings)

    logger.info("startup.checks_passed", results=results)
    _print_banner(info)

    return info


def _check_encryption_key(settings: Any) -> None:
    """Verify ENCRYPTION_KEY is set and is a valid Fernet key."""
    raw = settings.encryption_key.get_secret_value()
    if not raw or len(raw) < 32:
        raise StartupCheckError(
            "STARTUP FAILED: ENCRYPTION_KEY is missing or too short. "
            "Generate one with: python -c \"from cryptography.fernet import "
            "Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        from cryptography.fernet import Fernet

        Fernet(raw.encode("utf-8"))
    except Exception as exc:
        raise StartupCheckError(
            f"STARTUP FAILED: ENCRYPTION_KEY is not a valid Fernet key. {exc}"
        ) from exc


def _check_jwt_secret(settings: Any) -> None:
    """Verify JWT_SECRET is set and minimum 32 characters."""
    raw = settings.jwt_secret.get_secret_value()
    if not raw or len(raw) < 32:
        raise StartupCheckError(
            "STARTUP FAILED: JWT_SECRET is missing or too short (min 32 chars). "
            "Generate with: openssl rand -hex 32"
        )


async def _check_database(settings: Any) -> None:
    """Try connecting to the database."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
    except Exception as exc:
        raise StartupCheckError(
            f"STARTUP FAILED: Database not reachable at {settings.database_url.split('@')[-1]}. "
            f"Check DATABASE_URL. Error: {exc}"
        ) from exc


async def _check_redis(settings: Any) -> None:
    """Try pinging Redis."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
    except Exception as exc:
        raise StartupCheckError(
            f"STARTUP FAILED: Redis not reachable at {settings.redis_url}. "
            f"Check REDIS_URL. Error: {exc}"
        ) from exc


def _system_info(settings: Any) -> dict[str, Any]:
    """Gather system info for the startup banner."""
    return {
        "python_version": platform.python_version(),
        "fastapi_version": fastapi.__version__,
        "environment": settings.environment.value,
        "database": settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
        "redis": settings.redis_url,
        "platform": f"{platform.system()} {platform.release()}",
    }


def _print_banner(info: dict[str, Any]) -> None:
    """Print startup banner with system info."""
    logger.info("startup.banner", banner=_BANNER.strip())
    logger.info(
        "startup.info",
        python=info["python_version"],
        fastapi=info["fastapi_version"],
        environment=info["environment"],
        platform_os=info["platform"],
    )


__all__ = ["StartupCheckError", "run_startup_checks"]
