"""Sentry init + PII-scrub unit tests.

The init tests run regardless of whether ``sentry-sdk`` is on the
path — they only assert the no-op contract when DSN / package is
missing. The PII-scrub tests don't touch Sentry at all; they
exercise :func:`scrub_event_for_pii` as a pure dict-in / dict-out
function.
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

import pytest

from app.observability.sentry import (
    init_sentry,
    scrub_event_for_pii,
)

# ─── init contract ────────────────────────────────────────────────────


def test_init_returns_false_when_dsn_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No DSN → init is a silent no-op + returns False."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry() is False


def test_init_returns_false_when_package_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If sentry-sdk wasn't installed (the dev/test default), init
    short-circuits before any SDK call."""
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/1")
    with patch("app.observability.sentry.sentry_sdk", None):
        assert init_sentry() is False


def test_init_succeeds_when_dsn_set_and_package_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the SDK is present and a DSN is set, init forwards to
    ``sentry_sdk.init`` with the scrubber wired in. Uses a stub SDK
    so the test doesn't depend on ``sentry-sdk`` being installed."""

    class _StubSDK:
        last_kwargs: ClassVar[dict[str, object]] = {}

        @classmethod
        def init(cls, **kwargs: object) -> None:
            cls.last_kwargs = kwargs

    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.delenv("SENTRY_PROFILES_SAMPLE_RATE", raising=False)

    with patch("app.observability.sentry.sentry_sdk", _StubSDK):
        assert init_sentry() is True

    kwargs = _StubSDK.last_kwargs
    assert kwargs["dsn"] == "https://fake@sentry.io/1"
    assert kwargs["environment"] == "staging"
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["profiles_sample_rate"] == 0.0
    assert kwargs["send_default_pii"] is False
    assert kwargs["before_send"] is scrub_event_for_pii


def test_init_clamps_invalid_sample_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A garbage sample-rate env falls back to the default rather
    than crashing."""

    class _StubSDK:
        last_kwargs: ClassVar[dict[str, object]] = {}

        @classmethod
        def init(cls, **kwargs: object) -> None:
            cls.last_kwargs = kwargs

    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/1")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "not-a-number")
    monkeypatch.setenv("SENTRY_PROFILES_SAMPLE_RATE", "5.0")  # out of range

    with patch("app.observability.sentry.sentry_sdk", _StubSDK):
        assert init_sentry() is True

    assert _StubSDK.last_kwargs["traces_sample_rate"] == 0.1
    assert _StubSDK.last_kwargs["profiles_sample_rate"] == 0.0


# ─── PII scrubber ─────────────────────────────────────────────────────


def test_scrub_strips_authorization_header() -> None:
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer eyJhbGc...",
                "X-API-Key": "sk-prod-123",
                "Cookie": "session=abc; refresh=def",
                "Accept": "application/json",
            },
            "url": "https://api.tradetri.in/v1/strategies",
        }
    }
    out = scrub_event_for_pii(event)
    assert out is not None
    headers = out["request"]["headers"]
    assert headers["Authorization"] == "[scrubbed]"
    assert headers["X-API-Key"] == "[scrubbed]"
    assert headers["Cookie"] == "[scrubbed]"
    # Non-sensitive header passes through unchanged.
    assert headers["Accept"] == "application/json"


def test_scrub_anonymises_user_email() -> None:
    event = {"user": {"id": "abc-123", "email": "rohan@example.com"}}
    out = scrub_event_for_pii(event)
    assert out is not None
    assert out["user"]["email"] == "[user]@[example.com]"
    assert out["user"]["id"] == "abc-123"  # id passes through


def test_scrub_strips_phone_number_fields() -> None:
    event = {
        "user": {
            "id": "u1",
            "phone": "+919876543210",
            "phone_number": "9876543210",
        }
    }
    out = scrub_event_for_pii(event)
    assert out is not None
    assert out["user"]["phone"] == "[scrubbed]"
    assert out["user"]["phone_number"] == "[scrubbed]"


def test_scrub_redacts_token_query_params() -> None:
    event = {
        "request": {
            "url": "https://api.tradetri.in/callback?access_token=abc123&user=u1"
        }
    }
    out = scrub_event_for_pii(event)
    assert out is not None
    url = out["request"]["url"]
    assert "access_token=[scrubbed]" in url
    assert "user=u1" in url


def test_scrub_drops_body_for_sensitive_endpoints() -> None:
    event = {
        "request": {
            "url": "https://api.tradetri.in/auth/login",
            "data": {"email": "x@y", "password": "hunter2"},
        }
    }
    out = scrub_event_for_pii(event)
    assert out is not None
    assert out["request"]["data"] == "[scrubbed: sensitive endpoint]"


def test_scrub_strips_inline_email_in_breadcrumbs() -> None:
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "message": "Sent welcome email to rohan@x.com",
                    "data": {"to": "rohan@x.com"},
                }
            ]
        }
    }
    out = scrub_event_for_pii(event)
    assert out is not None
    crumb = out["breadcrumbs"]["values"][0]
    assert "[user]@[x.com]" in crumb["message"]
    assert crumb["data"]["to"] == "[user]@[x.com]"


def test_scrub_handles_missing_request_envelope() -> None:
    """Events without a ``request`` block (e.g. raw exceptions from
    a worker) pass through cleanly."""
    event = {"message": "Background job failed"}
    out = scrub_event_for_pii(event)
    assert out is not None
    assert out["message"] == "Background job failed"


def test_scrub_redacts_inline_phone_in_message() -> None:
    event = {"message": "OTP delivery to 9876543210 failed"}
    out = scrub_event_for_pii(event)
    assert out is not None
    assert out["message"] == "OTP delivery to [scrubbed-phone] failed"


def test_scrub_does_not_mangle_long_arbitrary_integers() -> None:
    """The phone regex requires a non-digit boundary, so a row id
    like ``99876543210123`` (14 digits) shouldn't be hit."""
    event = {"message": "Strategy 99876543210123 errored"}
    out = scrub_event_for_pii(event)
    assert out is not None
    assert "[scrubbed-phone]" not in out["message"]


# ─── Defensive smoke ─────────────────────────────────────────────────


def test_scrub_is_idempotent_on_empty_event() -> None:
    out = scrub_event_for_pii({})
    assert out is not None
    assert out == {}


def test_init_does_not_crash_when_environment_variable_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No SENTRY_ENVIRONMENT + no ENVIRONMENT — falls back to the
    'development' default without raising. ``monkeypatch.delenv``
    restores the original env after the test so later tests in the
    session don't inherit a polluted ``os.environ``."""
    for key in ("SENTRY_DSN", "SENTRY_ENVIRONMENT", "ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    assert init_sentry() is False
