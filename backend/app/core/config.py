"""Typed runtime settings, loaded from ``.env`` via pydantic-settings v2.

A single :class:`Settings` instance is exposed through :func:`get_settings`,
which is ``lru_cache``-wrapped so the same object is reused everywhere
(important — Fernet ciphers and DB engines must not be reconstructed per
request).

Tests that need different values should call ``get_settings.cache_clear()``
between cases.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment — gates dev-only conveniences."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(StrEnum):
    """Mirror of stdlib levels — repeated as an enum so config can be typed."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Runtime configuration.

    Field naming follows env-var convention (``UPPER_CASE``) with
    ``case_sensitive=False`` so ``MyVar`` and ``MYVAR`` both bind.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Runtime ────────────────────────────────────────────────────────
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: LogLevel = LogLevel.INFO

    # ─── Security ───────────────────────────────────────────────────────
    encryption_key: SecretStr = Field(
        ...,
        description=(
            "Fernet key used to encrypt broker credentials at rest. "
            "Generate with: python -c \"from cryptography.fernet import "
            "Fernet; print(Fernet.generate_key().decode())\""
        ),
    )
    jwt_secret: SecretStr = Field(
        ...,
        description="HS256 signing key for API tokens. Generate with `openssl rand -hex 32`.",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    webhook_hmac_secret: SecretStr = Field(
        default=SecretStr("dev-hmac-secret-change-me"),
        description="Base secret for TradingView webhook HMAC verification.",
    )

    # ─── Database ───────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://trading_bridge:change-me@localhost:5432/trading_bridge",
        description="SQLAlchemy async URL.",
    )

    # ─── Redis ──────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ─── Fyers ──────────────────────────────────────────────────────────
    fyers_app_id: str = Field(default="", description="Platform-level Fyers app ID.")
    fyers_app_secret: SecretStr = Field(
        default=SecretStr(""),
        description="Platform-level Fyers app secret.",
    )
    fyers_redirect_uri: str = Field(
        default="https://tradingbridge.in/api/brokers/fyers/callback",
        description="OAuth redirect registered with Fyers.",
    )

    # ─── Validators ─────────────────────────────────────────────────────

    @field_validator("encryption_key")
    @classmethod
    def _validate_fernet_key(cls, value: SecretStr) -> SecretStr:
        """Fernet keys are 32 url-safe-b64 bytes — fail loudly on garbage.

        We only check shape here; ``Fernet(value)`` will catch byte-level
        corruption in :mod:`app.core.security`.
        """
        raw = value.get_secret_value()
        if not raw or len(raw) < 32:
            raise ValueError(
                "ENCRYPTION_KEY missing or too short. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton.

    Cached so Fernet ciphers, engines, and HTTP clients constructed from
    settings can be safely module-globals. Call ``.cache_clear()`` in
    tests when overriding env vars between cases.

    In ``ENVIRONMENT=test`` the ``.env`` file is explicitly bypassed — tests
    must control every variable through ``monkeypatch`` so local dev secrets
    cannot leak in.
    """
    if os.environ.get("ENVIRONMENT", "").lower() == "test":
        return Settings(_env_file=None)  # type: ignore[call-arg]
    return Settings()  # type: ignore[call-arg]


__all__ = ["Environment", "LogLevel", "Settings", "get_settings"]
