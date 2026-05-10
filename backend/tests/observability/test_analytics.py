"""Analytics init + track_event behaviour tests.

Same posture as the Sentry tests — substitute a stub PostHog
client into the module's ``posthog`` reference, exercise the
public API, assert the contract.
"""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from app.observability import analytics
from app.observability.analytics import (
    init_analytics,
    is_initialised,
    track_event,
)
from app.observability.pii_scrubber import hash_user_id


@pytest.fixture(autouse=True)
def _reset_analytics_state() -> None:
    """Each test starts with the module flagged as un-initialised."""
    analytics._reset_for_tests()
    yield
    analytics._reset_for_tests()


# ─── Init contract ────────────────────────────────────────────────────


def test_init_returns_false_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No API key → silent no-op + returns False."""
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")
    assert init_analytics() is False
    assert is_initialised() is False


def test_init_returns_false_when_package_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``posthog`` isn't installed, init short-circuits."""
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")
    with patch("app.observability.analytics.posthog", None):
        assert init_analytics() is False


def test_init_returns_false_when_explicitly_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ANALYTICS_ENABLED=false`` short-circuits even with an
    API key set — used in dev / staging when traffic shouldn't
    pollute the prod project."""
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")

    class _StubPosthog:
        api_key: ClassVar[str | None] = None
        host: ClassVar[str | None] = None

    with patch("app.observability.analytics.posthog", _StubPosthog):
        assert init_analytics() is False


def test_init_succeeds_when_api_key_set_and_package_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test_123")
    monkeypatch.setenv("POSTHOG_HOST", "https://eu.posthog.com")
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")

    class _StubPosthog:
        api_key: ClassVar[str | None] = None
        host: ClassVar[str | None] = None
        debug: ClassVar[bool] = True
        captures: ClassVar[list[dict[str, Any]]] = []

        @classmethod
        def capture(
            cls,
            *,
            distinct_id: str,
            event: str,
            properties: dict[str, Any],
        ) -> None:
            cls.captures.append(
                {"distinct_id": distinct_id, "event": event, "properties": properties}
            )

    with patch("app.observability.analytics.posthog", _StubPosthog):
        assert init_analytics() is True
        assert _StubPosthog.api_key == "phc_test_123"
        assert _StubPosthog.host == "https://eu.posthog.com"
        assert _StubPosthog.debug is False  # forced off


def test_init_defaults_to_off_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``ANALYTICS_ENABLED`` + non-prod ``ENVIRONMENT`` → off."""
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
    monkeypatch.delenv("ANALYTICS_ENABLED", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    class _StubPosthog:
        api_key: ClassVar[str | None] = None

    with patch("app.observability.analytics.posthog", _StubPosthog):
        assert init_analytics() is False


# ─── track_event ──────────────────────────────────────────────────────


def test_track_event_no_op_before_init() -> None:
    """Pre-init calls don't raise + don't emit."""
    track_event("user-1", "test_event", {"mode": "beginner"})
    # No assertion target other than "no exception".


def test_track_event_calls_posthog_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When initialised, track_event forwards to posthog.capture
    with hashed user id + scrubbed properties."""
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_x")
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")

    captured: list[dict[str, Any]] = []

    class _StubPosthog:
        api_key: ClassVar[str | None] = None
        host: ClassVar[str | None] = None
        debug: ClassVar[bool] = True

        @classmethod
        def capture(
            cls,
            *,
            distinct_id: str,
            event: str,
            properties: dict[str, Any],
        ) -> None:
            captured.append(
                {
                    "distinct_id": distinct_id,
                    "event": event,
                    "properties": properties,
                }
            )

    with patch("app.observability.analytics.posthog", _StubPosthog):
        init_analytics()
        track_event(
            "user-1",
            "strategy_created",
            {"mode": "expert", "email": "x@y", "indicator_count": 3},
        )

    assert len(captured) == 1
    record = captured[0]
    assert record["event"] == "strategy_created"
    # User id arrives hashed.
    assert record["distinct_id"] == hash_user_id("user-1")
    # Email scrubbed; non-PII fields preserved.
    assert "email" not in record["properties"]
    assert record["properties"]["mode"] == "expert"
    assert record["properties"]["indicator_count"] == 3


def test_track_event_swallows_sdk_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exception inside posthog.capture must not propagate.
    The business path that called track_event keeps running."""
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_x")
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")

    class _ExplodingPosthog:
        api_key: ClassVar[str | None] = None
        host: ClassVar[str | None] = None
        debug: ClassVar[bool] = True

        @classmethod
        def capture(cls, **kwargs: Any) -> None:
            raise RuntimeError("posthog server is down")

    with patch("app.observability.analytics.posthog", _ExplodingPosthog):
        init_analytics()
        # Should NOT raise.
        track_event("user-1", "test_event", {})


def test_track_event_skips_when_init_short_circuited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Init returned False → track_event is a no-op even if a
    PostHog stub is wired in."""
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)

    captured: list[Any] = []

    class _StubPosthog:
        api_key: ClassVar[str | None] = None
        host: ClassVar[str | None] = None
        debug: ClassVar[bool] = True

        @classmethod
        def capture(cls, **kwargs: Any) -> None:
            captured.append(kwargs)

    with patch("app.observability.analytics.posthog", _StubPosthog):
        init_analytics()
        track_event("user-1", "test_event", {})

    assert captured == []


def test_track_event_with_none_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``properties=None`` is allowed and emits an empty dict."""
    monkeypatch.setenv("POSTHOG_API_KEY", "phc_x")
    monkeypatch.setenv("ANALYTICS_ENABLED", "true")

    captured: list[dict[str, Any]] = []

    class _StubPosthog:
        api_key: ClassVar[str | None] = None
        host: ClassVar[str | None] = None
        debug: ClassVar[bool] = True

        @classmethod
        def capture(
            cls,
            *,
            distinct_id: str,
            event: str,
            properties: dict[str, Any],
        ) -> None:
            captured.append(properties)

    with patch("app.observability.analytics.posthog", _StubPosthog):
        init_analytics()
        track_event("user-1", "page_viewed")

    assert captured == [{}]
