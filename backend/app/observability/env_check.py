"""Production env-var validation — fails fast on misconfiguration.

Called from ``app.main`` at startup when ``ENVIRONMENT=production``.
The required-set is a deliberately small list of vars whose absence
WILL break the app — anything optional logs a warning instead of
crashing.

Adding a new required var:
    1. Add to ``REQUIRED_PRODUCTION_ENV`` with a one-line ``description``.
    2. Update ``backend/.env.example`` + ``backend/.env.production.example``.
    3. Mention the var in ``PRODUCTION_DEPLOY.md`` under the
       "Required env vars" section.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("app.observability.env_check")


class EnvValidationError(RuntimeError):
    """Raised when production startup is missing a required env var."""


@dataclass(frozen=True)
class EnvVar:
    name: str
    description: str


#: Vars whose absence in production is fatal. App startup raises
#: :class:`EnvValidationError` and the orchestrator should restart.
REQUIRED_PRODUCTION_ENV: tuple[EnvVar, ...] = (
    EnvVar(
        name="DATABASE_URL",
        description="Postgres async URL (postgresql+asyncpg://...). The app's "
        "DB engine refuses to start without it.",
    ),
    EnvVar(
        name="REDIS_URL",
        description="Redis URL (redis://host:port/db). Required for "
        "rate-limiting + caching.",
    ),
    EnvVar(
        name="JWT_SECRET",
        description="HS256 signing secret for access/refresh tokens. "
        "Auto-rotates on every token issuance, so a missing value "
        "is a hard fail at startup.",
    ),
    EnvVar(
        name="ENCRYPTION_KEY",
        description="Fernet key used to encrypt broker credentials at "
        "rest. Generate via "
        "``python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\"``.",
    ),
    EnvVar(
        name="WEBHOOK_HMAC_SECRET",
        description="HMAC secret base for TradingView webhook signature "
        "verification. Without this every webhook 401s.",
    ),
)


#: Vars whose absence is non-fatal but worth surfacing at startup.
OPTIONAL_PRODUCTION_ENV: tuple[EnvVar, ...] = (
    EnvVar(
        name="SENTRY_DSN",
        description="Sentry project DSN. Without it error tracking is "
        "disabled — strongly recommended for production.",
    ),
    EnvVar(
        name="DHAN_ACCESS_TOKEN",
        description="Dhan broker live-data token. Live trading + "
        "real-time candle backtests stay unavailable until set.",
    ),
    EnvVar(
        name="CORS_ALLOW_ORIGINS",
        description="JSON array of allowed origins. Defaults to "
        "permissive dev origins — set explicitly in production.",
    ),
    EnvVar(
        name="CELERY_BROKER_URL",
        description="Celery broker URL. Background-task workers fail "
        "to start without it.",
    ),
)


def validate_production_env(
    *,
    env_getter: Callable[[str], str | None] | None = None,
) -> None:
    """Assert every :data:`REQUIRED_PRODUCTION_ENV` var is set when
    ``ENVIRONMENT=production``. Logs warnings for missing
    :data:`OPTIONAL_PRODUCTION_ENV` vars.

    No-op when ``ENVIRONMENT`` is anything other than ``production``
    (development / staging / unset).

    The optional ``env_getter`` parameter is a hook for tests —
    pass a ``dict.get`` style callable to substitute a test env. In
    production it defaults to ``os.environ.get``.
    """
    getter: Callable[[str], str | None] = env_getter or os.environ.get
    environment = (getter("ENVIRONMENT") or "").lower()
    if environment != "production":
        return

    missing_required: list[str] = []
    for var in REQUIRED_PRODUCTION_ENV:
        value = getter(var.name)
        if not value:
            missing_required.append(var.name)
            logger.error(
                "env.missing_required",
                # ``var_name`` because ``name`` collides with the
                # LogRecord's built-in ``name`` attribute.
                extra={"var_name": var.name, "description": var.description},
            )

    if missing_required:
        raise EnvValidationError(
            "Production startup blocked — missing required env vars: "
            + ", ".join(sorted(missing_required))
        )

    for var in OPTIONAL_PRODUCTION_ENV:
        value = getter(var.name)
        if not value:
            logger.warning(
                "env.missing_optional",
                extra={"var_name": var.name, "description": var.description},
            )

    logger.info(
        "env.production_validated",
        extra={
            "required_count": len(REQUIRED_PRODUCTION_ENV),
            "optional_count": len(OPTIONAL_PRODUCTION_ENV),
        },
    )


__all__ = [
    "OPTIONAL_PRODUCTION_ENV",
    "REQUIRED_PRODUCTION_ENV",
    "EnvValidationError",
    "EnvVar",
    "validate_production_env",
]
