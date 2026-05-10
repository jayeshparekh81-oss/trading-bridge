"""PostHog analytics integration — graceful no-op without API key.

Same posture as :mod:`sentry`:

    1. ``import posthog`` is wrapped in ``try / except ImportError``
       so the module loads cleanly with or without the package on
       disk. Without the package, every public call is a silent
       no-op.
    2. ``init_analytics()`` short-circuits when ``POSTHOG_API_KEY``
       is missing or analytics are explicitly disabled via
       ``ANALYTICS_ENABLED=false``.
    3. ``track_event`` itself never raises. Any error from the
       PostHog SDK is caught + logged; the calling business path
       MUST NOT fail because the analytics pipe is misbehaving.

Privacy contract (paired with :mod:`pii_scrubber`):

    * ``user_id`` is SHA-256 hashed before leaving the process.
    * Properties are run through :func:`scrub_properties_dict` so
      a stray ``email`` or ``phone`` field is dropped.
    * No P&L magnitudes are emitted — aggregate-percentage stats
      (``win_rate``) only.

Env vars:

    POSTHOG_API_KEY        (optional) — without it, no init.
    POSTHOG_HOST           (optional) — default
                                       ``https://app.posthog.com``.
    ANALYTICS_ENABLED      (optional) — ``false`` short-circuits
                                       even when API key is set.
                                       Default: ``true`` in
                                       production, ``false`` else.
    ANALYTICS_SALT         (optional) — see
                                       :mod:`pii_scrubber`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.observability.pii_scrubber import (
    hash_user_id,
    scrub_properties_dict,
)

# Lazy import — module loads cleanly when ``posthog`` isn't
# installed (the Phase 1 launch posture). ``init_analytics``
# bails before touching the SDK if it's None.
try:
    import posthog  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — exercised when the package is absent
    posthog = None

logger = logging.getLogger("app.observability.analytics")

#: Module-level state — flipped to True once init has run with a
#: usable API key. Subsequent ``track_event`` calls use this to
#: decide whether to forward at all.
_INITIALISED: bool = False


def init_analytics() -> bool:
    """Initialise PostHog from env vars. Returns ``True`` on
    success, ``False`` on any short-circuit.

    Called from the FastAPI lifespan startup. Safe to call
    multiple times — subsequent calls are no-ops once initialised.
    """
    global _INITIALISED

    if posthog is None:
        logger.info(
            "analytics.skip", extra={"reason": "posthog package not installed"}
        )
        return False

    if not _is_enabled():
        logger.info("analytics.skip", extra={"reason": "ANALYTICS_ENABLED is false"})
        return False

    api_key = os.environ.get("POSTHOG_API_KEY", "").strip()
    if not api_key:
        logger.info("analytics.skip", extra={"reason": "POSTHOG_API_KEY unset"})
        return False

    host = os.environ.get("POSTHOG_HOST", "https://app.posthog.com")

    try:
        posthog.api_key = api_key
        posthog.host = host
        # Disable PostHog's own debug noise unless the operator
        # asks for it. Without this PostHog logs every flush at INFO.
        if hasattr(posthog, "debug"):
            posthog.debug = False
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "analytics.init_failed", extra={"error": str(exc)}, exc_info=exc
        )
        return False

    _INITIALISED = True
    logger.info("analytics.initialised", extra={"host": host})
    return True


def track_event(
    user_id: str,
    event_name: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Record one analytics event. Never raises — any failure is
    swallowed and logged so the calling business path never
    inherits an analytics-pipe outage.

    The user id is hashed before emission; properties are scrubbed
    of PII / amount fields. If analytics aren't initialised, the
    call is a silent no-op.
    """
    if not _INITIALISED or posthog is None:
        return

    try:
        hashed_user = hash_user_id(user_id)
        clean_props = scrub_properties_dict(properties or {})
        posthog.capture(
            distinct_id=hashed_user,
            event=event_name,
            properties=clean_props,
        )
    except Exception as exc:  # pragma: no cover - defensive
        # Crucial: never let an analytics failure surface to the
        # caller. Log + carry on.
        logger.warning(
            "analytics.capture_failed",
            extra={"event": event_name, "error": str(exc)},
        )


def is_initialised() -> bool:
    """Read the init state for tests + admin tooling."""
    return _INITIALISED


def _reset_for_tests() -> None:
    """Test-only — flip the init flag back so a stale state from
    a prior test doesn't leak into the next one."""
    global _INITIALISED
    _INITIALISED = False


def _is_enabled() -> bool:
    """Resolve ``ANALYTICS_ENABLED`` with the right defaults per
    environment."""
    raw = os.environ.get("ANALYTICS_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"true", "1", "yes", "on"}
    # Default: production = on, everything else = off.
    return (os.environ.get("ENVIRONMENT") or "").lower() == "production"


__all__ = [
    "init_analytics",
    "is_initialised",
    "track_event",
]
