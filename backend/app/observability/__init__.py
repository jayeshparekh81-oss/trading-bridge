"""Observability primitives — Sentry init, env validation,
analytics tracking.

Public surface:

    init_sentry()              — call once at app startup; no-op when
                                 ``SENTRY_DSN`` is missing or the
                                 ``sentry-sdk`` package isn't installed.
    init_analytics()           — same posture for PostHog: no-op when
                                 ``POSTHOG_API_KEY`` is missing or
                                 ``ANALYTICS_ENABLED=false`` or the
                                 ``posthog`` package isn't installed.
    track_event()              — emit an analytics event. Always
                                 swallows exceptions so business paths
                                 never inherit an analytics-pipe outage.
    validate_production_env()  — assert required env vars are set when
                                 ``ENVIRONMENT=production``; logs
                                 warnings for missing optional vars.
"""

from __future__ import annotations

from app.observability.analytics import (
    init_analytics,
    track_event,
)
from app.observability.analytics import (
    is_initialised as analytics_initialised,
)
from app.observability.env_check import (
    OPTIONAL_PRODUCTION_ENV,
    REQUIRED_PRODUCTION_ENV,
    EnvValidationError,
    validate_production_env,
)
from app.observability.pii_scrubber import (
    hash_resource_id,
    hash_user_id,
    scrub_properties_dict,
)
from app.observability.sentry import init_sentry, scrub_event_for_pii

__all__ = [
    "OPTIONAL_PRODUCTION_ENV",
    "REQUIRED_PRODUCTION_ENV",
    "EnvValidationError",
    "analytics_initialised",
    "hash_resource_id",
    "hash_user_id",
    "init_analytics",
    "init_sentry",
    "scrub_event_for_pii",
    "scrub_properties_dict",
    "track_event",
    "validate_production_env",
]
