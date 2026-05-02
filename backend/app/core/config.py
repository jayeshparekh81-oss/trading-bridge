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
from decimal import Decimal
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

    # ─── Dhan ───────────────────────────────────────────────────────────
    dhan_api_base_url: str = Field(
        default="https://api.dhan.co/v2",
        description="Dhan HQ REST base URL.",
    )
    dhan_scrip_master_url: str = Field(
        default="https://images.dhan.co/api-data/api-scrip-master.csv",
        description="Instrument master CSV (symbol ↔ securityId mapping).",
    )

    # ─── AlgoMitra (Anthropic Claude) ───────────────────────────────────
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Anthropic API key for AlgoMitra chat. Empty disables AI.",
    )
    algomitra_model: str = Field(
        default="claude-sonnet-4-6",
        description="Claude model ID for AlgoMitra. Use claude-sonnet-4-6 (default) or claude-opus-4-7.",
    )
    algomitra_daily_message_limit: int = Field(
        default=50,
        description="Per-user daily AI message cap (Phase 1B free tier).",
    )
    algomitra_max_history: int = Field(
        default=10,
        description="How many prior messages to send to Claude as context.",
    )
    algomitra_usd_to_inr: float = Field(
        default=84.0,
        description="USD→INR conversion rate for cost logging. Update quarterly.",
    )

    # ─── Safety gates ───────────────────────────────────────────────────
    kill_switch_check_enabled: bool = True
    circuit_breaker_enabled: bool = True

    # ─── Strategy execution engine ─────────────────────────────────────
    strategy_paper_mode: bool = Field(
        default=True,
        description=(
            "When True, the strategy executor simulates fills instead of "
            "calling the broker. Default ON; flip to False only after the "
            "Wed paper-mode test passes."
        ),
    )
    strategy_position_poll_seconds: int = Field(
        default=5,
        description=(
            "Position-manager polling interval in seconds. 5 s is fine for "
            "1-2 strategies; raise it if Redis/broker QPS becomes a concern."
        ),
        gt=0,
    )
    tradingview_trusted_ips: list[str] = Field(
        default=[
            "52.89.214.238",
            "34.212.75.30",
            "54.218.53.128",
            "52.32.178.7",
        ],
        description=(
            "TradingView's published webhook egress IPs. Requests from "
            "these addresses bypass HMAC verification on the strategy "
            "webhook — TV's free tier cannot sign payloads. ALL OTHER "
            "gates (rate limit, idempotency, kill switch, user-active, "
            "max daily trades) still apply. Override via env JSON list, "
            "e.g. ``TRADINGVIEW_TRUSTED_IPS=[\"1.2.3.4\",\"5.6.7.8\"]``."
        ),
    )
    reconciliation_poll_seconds: int = Field(
        default=60,
        description=(
            "Order-reconciliation cron interval. Cross-checks DB open "
            "positions against ``broker.get_positions()`` for every active "
            "broker credential and fires a CRITICAL Telegram alert on "
            "drift. No-op when ``strategy_paper_mode`` is True — there is "
            "no broker side to reconcile against."
        ),
        gt=0,
    )
    pre_trade_margin_per_lot_inr: Decimal = Field(
        default=Decimal("100000"),
        description=(
            "Coarse pre-trade margin floor — rejects an order if available "
            "funds < quantity × this value × 1.10 (10 %% slippage buffer). "
            "NOT a real margin calculator: the broker's margin engine still "
            "owns the final word. Default ₹1,00,000 / lot is a safe lower "
            "bound for NIFTY / BANKNIFTY intraday F&O. Tune per environment."
        ),
        gt=Decimal("0"),
    )

    # ─── Security policy ────────────────────────────────────────────────
    max_request_body_size: int = Field(
        default=1_048_576,
        description="Reject HTTP bodies larger than this (bytes).",
    )
    brute_force_max_attempts: int = 5
    brute_force_lock_minutes: int = 60
    session_max_age_hours: int = 24
    trusted_proxy_ips: list[str] = Field(
        default_factory=list,
        description=(
            "IPs/CIDRs whose X-Forwarded-For we trust. Empty = do not honour "
            "forwarded headers; use peer IP directly."
        ),
    )
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "https://tradetri.com",
            "https://www.tradetri.com",
            "https://trading-bridge-olive.vercel.app",
            "https://trading-bridge-five.vercel.app",
            "http://localhost:3000",
        ],
        description="Origins allowed by CORS.",
    )

    # ─── Market schedule (IST wall-clock) ───────────────────────────────
    market_open_time: str = "09:15"
    market_close_time: str = "15:30"
    auto_square_off_time: str = "15:15"

    # ─── Email (AWS SES) ───────────────────────────────────────────────
    aws_ses_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    from_email: str = "alerts@tradingbridge.in"

    # ─── Email (SMTP fallback for dev) ─────────────────────────────────
    smtp_host: str = "localhost"
    smtp_port: int = 1025

    # ─── Telegram Bot ──────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_enabled: bool = False
    telegram_alert_chat_id: str = Field(
        default="",
        description=(
            "Operator alert chat ID — receives system-level alerts "
            "(orders, kill-switch trips, background errors). Distinct "
            "from per-user ``user.telegram_chat_id`` which is for end-"
            "user notifications. Empty string disables operator alerts "
            "(graceful no-op so dev/staging without a configured bot "
            "do not spam logs)."
        ),
    )

    # ─── Auth ──────────────────────────────────────────────────────────
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # ─── Celery ─────────────────────────────────────────────────────────
    celery_broker_url: str = ""
    celery_result_backend: str = ""

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
