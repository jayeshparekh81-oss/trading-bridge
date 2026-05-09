"""Observability primitives — Sentry init, env validation, etc.

Public surface:

    init_sentry()              — call once at app startup; no-op when
                                 ``SENTRY_DSN`` is missing or the
                                 ``sentry-sdk`` package isn't
                                 installed.
    validate_production_env()  — assert required env vars are set when
                                 ``ENVIRONMENT=production``; logs
                                 warnings for missing optional vars.
"""

from __future__ import annotations

from app.observability.env_check import (
    OPTIONAL_PRODUCTION_ENV,
    REQUIRED_PRODUCTION_ENV,
    EnvValidationError,
    validate_production_env,
)
from app.observability.sentry import init_sentry, scrub_event_for_pii

__all__ = [
    "OPTIONAL_PRODUCTION_ENV",
    "REQUIRED_PRODUCTION_ENV",
    "EnvValidationError",
    "init_sentry",
    "scrub_event_for_pii",
    "validate_production_env",
]
