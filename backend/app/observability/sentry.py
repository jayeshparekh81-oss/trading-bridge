"""Sentry initialization — Phase 1 of the production observability story.

Two design constraints make this module import-safe even before
``sentry-sdk`` is installed:

    1. The ``import sentry_sdk`` statement is wrapped in a
       ``try/except ImportError`` so the module loads cleanly with
       or without the package. The init function is then a silent
       no-op when the package isn't on the path.
    2. ``init_sentry()`` itself never raises — it logs a warning
       and returns if any setup step fails. App startup MUST NOT
       crash when Sentry isn't reachable.

Env vars consumed:

    SENTRY_DSN                       (optional) — if missing, init is a no-op.
    SENTRY_ENVIRONMENT               (optional) — default ``ENVIRONMENT`` or "development".
    SENTRY_TRACES_SAMPLE_RATE        (optional, float, default 0.1)
    SENTRY_PROFILES_SAMPLE_RATE      (optional, float, default 0.0)
    SENTRY_RELEASE                   (optional) — git short SHA in CI / "dev" locally.

PII safety:

    * ``send_default_pii=False`` — Sentry SDK won't auto-capture
      cookies / IP addresses / request bodies.
    * ``before_send`` hook (:func:`scrub_event_for_pii`) strips
      Authorization headers, anonymises emails to
      ``[user]@[domain]``, masks Indian phone-number patterns, and
      strips query-string token values.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

# Lazy import — keeps the module loadable when sentry-sdk isn't
# installed. ``init_sentry`` checks for ``sentry_sdk is None`` and
# bails before touching the SDK surface.
try:
    import sentry_sdk  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — exercised when the package is absent
    sentry_sdk = None

logger = logging.getLogger("app.observability.sentry")


# ─── Public API ────────────────────────────────────────────────────────


def init_sentry() -> bool:
    """Initialise Sentry from env vars. Returns ``True`` on success,
    ``False`` on any short-circuit (package missing, DSN missing,
    init exception).

    Safe to call multiple times — subsequent calls are no-ops if the
    SDK is already initialised.
    """
    if sentry_sdk is None:
        logger.info(
            "sentry.skip", extra={"reason": "sentry-sdk package not installed"}
        )
        return False

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("sentry.skip", extra={"reason": "SENTRY_DSN unset"})
        return False

    environment = os.environ.get(
        "SENTRY_ENVIRONMENT",
        os.environ.get("ENVIRONMENT", "development"),
    )
    traces_rate = _parse_float_env("SENTRY_TRACES_SAMPLE_RATE", default=0.1)
    profiles_rate = _parse_float_env("SENTRY_PROFILES_SAMPLE_RATE", default=0.0)
    release = os.environ.get("SENTRY_RELEASE")

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=traces_rate,
            profiles_sample_rate=profiles_rate,
            send_default_pii=False,
            before_send=scrub_event_for_pii,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "sentry.init_failed", extra={"error": str(exc)}, exc_info=exc
        )
        return False

    logger.info(
        "sentry.initialised",
        extra={
            "environment": environment,
            "traces_sample_rate": traces_rate,
            "profiles_sample_rate": profiles_rate,
            "release": release,
        },
    )
    return True


def scrub_event_for_pii(
    event: dict[str, Any], hint: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Sentry ``before_send`` hook — strip PII from outgoing events.

    Called by ``sentry_sdk`` before any event leaves the process.
    Pure dict-in / dict-out so the function is unit-testable without
    the SDK installed.
    """
    _ = hint  # currently unused; the SDK passes context we don't need.

    # ── Strip Authorization + Cookie headers from request envelope ──
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            for key in list(headers):
                if key.lower() in {"authorization", "cookie", "x-api-key"}:
                    headers[key] = "[scrubbed]"

        # Strip access_token / token / api_key query params on the URL.
        url = request.get("url")
        if isinstance(url, str):
            request["url"] = _scrub_url_tokens(url)

        # Strip the body for known sensitive endpoints.
        path = request.get("url") if isinstance(request.get("url"), str) else ""
        if isinstance(path, str) and any(
            sensitive in path
            for sensitive in (
                "/auth/login",
                "/auth/register",
                "/auth/password",
                "/brokers/",
            )
        ):
            request["data"] = "[scrubbed: sensitive endpoint]"

    # ── Anonymise the user payload ────────────────────────────────────
    user = event.get("user")
    if isinstance(user, dict):
        if "email" in user and isinstance(user["email"], str):
            user["email"] = _anonymise_email(user["email"])
        # Phone numbers under any of the common keys we use.
        for key in ("phone", "phone_number", "telephone"):
            if key in user and isinstance(user[key], str):
                user[key] = "[scrubbed]"
        # ``ip_address`` already suppressed via ``send_default_pii=False``,
        # but defensive scrub if a custom path set it.
        user.pop("ip_address", None)

    # ── Recurse breadcrumbs for inline emails / phones / tokens ──────
    breadcrumbs_field = event.get("breadcrumbs")
    breadcrumbs: list[Any] = []
    if isinstance(breadcrumbs_field, dict):
        values = breadcrumbs_field.get("values")
        if isinstance(values, list):
            breadcrumbs = values
    elif isinstance(breadcrumbs_field, list):
        breadcrumbs = breadcrumbs_field

    for crumb in breadcrumbs:
        if not isinstance(crumb, dict):
            continue
        message = crumb.get("message")
        if isinstance(message, str):
            crumb["message"] = _scrub_string_for_pii(message)
        data = crumb.get("data")
        if isinstance(data, dict):
            for key in list(data):
                if isinstance(data[key], str):
                    data[key] = _scrub_string_for_pii(data[key])

    # Top-level message scrub.
    if isinstance(event.get("message"), str):
        event["message"] = _scrub_string_for_pii(event["message"])

    return event


# ─── Helpers ───────────────────────────────────────────────────────────


def _parse_float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "sentry.bad_env", extra={"var_name": name, "raw": raw}
        )
        return default
    if value < 0 or value > 1:
        logger.warning(
            "sentry.bad_env_range",
            extra={"var_name": name, "raw": raw},
        )
        return default
    return value


_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
#: Indian-phone heuristic: 10 digits, optionally with +91 / 0 prefix.
#: Tightened to require a non-digit boundary so we don't mangle
#: every long integer that floats by.
_PHONE_RE = re.compile(r"\b(?:\+91|91|0)?[6-9]\d{9}\b")
#: Token-bearing query parameters.
_TOKEN_PARAM_RE = re.compile(
    r"((?:access_token|token|api_key|secret|jwt)=)[^&\s]+",
    re.IGNORECASE,
)


def _anonymise_email(email: str) -> str:
    match = _EMAIL_RE.fullmatch(email.strip())
    if not match:
        return "[scrubbed]"
    return f"[user]@[{match.group(2)}]"


def _scrub_url_tokens(url: str) -> str:
    return _TOKEN_PARAM_RE.sub(r"\1[scrubbed]", url)


def _scrub_string_for_pii(text: str) -> str:
    """Strip emails, phones, and token-bearing URL params from a
    free-form string (breadcrumb message, log message, etc.)."""
    text = _EMAIL_RE.sub(
        lambda m: f"[user]@[{m.group(2)}]", text
    )
    text = _PHONE_RE.sub("[scrubbed-phone]", text)
    text = _TOKEN_PARAM_RE.sub(r"\1[scrubbed]", text)
    return text
