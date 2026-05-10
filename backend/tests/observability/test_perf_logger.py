"""``SlowRequestLoggerMiddleware`` behavior tests.

The middleware ships in ``app/observability/perf_logger.py``. It
emits one structured ``request.slow`` log per request whose
end-to-end duration exceeds a threshold; fast requests must NOT
produce a log line at all (otherwise we'd dominate log volume).

We exercise the middleware against a minimal FastAPI app rather
than the full ``create_app()`` chain — keeps the tests fast and
isolates the assertion target. The slow path is induced by
``asyncio.sleep`` so we don't depend on machine-specific clock
behavior.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.perf_logger import (
    DEFAULT_THRESHOLD_MS,
    SlowRequestLoggerMiddleware,
)


def _build_app(threshold_ms: float | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        SlowRequestLoggerMiddleware, threshold_ms=threshold_ms
    )

    @app.get("/fast")
    async def _fast() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/slow")
    async def _slow() -> dict[str, bool]:
        # 60 ms so we're cleanly above the test's 20 ms threshold
        # without making the suite drag.
        await asyncio.sleep(0.06)
        return {"ok": True}

    @app.get("/boom")
    async def _boom() -> dict[str, bool]:
        await asyncio.sleep(0.06)
        raise RuntimeError("intentional")

    return app


@pytest.fixture
def caplog_logger(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """``structlog`` routes through stdlib logging; force the
    perf-logger's logger to ``WARNING`` so the test's ``caplog``
    captures emissions deterministically."""
    caplog.set_level(logging.WARNING, logger="app.observability.perf_logger")
    yield caplog


def _log_records_with_event(
    caplog: pytest.LogCaptureFixture, event: str
) -> list[logging.LogRecord]:
    """Filter caplog records by structlog event field (which lands
    in the message body when the test config doesn't process it
    further)."""
    return [r for r in caplog.records if event in r.getMessage()]


def test_default_threshold_constant() -> None:
    assert DEFAULT_THRESHOLD_MS == 500.0


def test_fast_request_does_not_log(
    caplog_logger: pytest.LogCaptureFixture,
) -> None:
    """A request that completes well under the threshold MUST NOT
    emit a slow-request log — otherwise the middleware would burn
    log budget on every healthcheck ping."""
    with TestClient(_build_app(threshold_ms=20.0)) as client:
        resp = client.get("/fast")
    assert resp.status_code == 200
    assert _log_records_with_event(caplog_logger, "request.slow") == []


def test_slow_request_emits_structured_log(
    caplog_logger: pytest.LogCaptureFixture,
) -> None:
    """A request slower than the threshold emits exactly one
    ``request.slow`` log with the structured fields the
    monitoring layer keys off."""
    with TestClient(_build_app(threshold_ms=20.0)) as client:
        resp = client.get("/slow")
    assert resp.status_code == 200
    records = _log_records_with_event(caplog_logger, "request.slow")
    assert len(records) == 1, [r.getMessage() for r in records]
    msg = records[0].getMessage()
    assert "/slow" in msg
    assert "GET" in msg
    assert "duration_ms" in msg
    assert "200" in msg or "status_code=200" in msg


def test_slow_request_that_raises_still_logs_failed_variant(
    caplog_logger: pytest.LogCaptureFixture,
) -> None:
    """If the downstream handler raises, the exception propagates
    BUT the middleware still emits ``request.slow_failed`` so we
    don't lose tail-latency attribution on errored requests."""
    app = _build_app(threshold_ms=20.0)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/boom")
    # FastAPI's default 500 surfaces because raise_server_exceptions=False
    assert resp.status_code == 500
    records = _log_records_with_event(caplog_logger, "request.slow_failed")
    assert len(records) == 1


def test_threshold_env_override(
    monkeypatch: pytest.MonkeyPatch,
    caplog_logger: pytest.LogCaptureFixture,
) -> None:
    """``PERF_SLOW_REQUEST_MS`` env var picks up at middleware
    construction time. We verify the constructor reads it by
    setting a high value and confirming the slow handler
    *doesn't* trigger a log."""
    monkeypatch.setenv("PERF_SLOW_REQUEST_MS", "5000")
    # Pass threshold_ms=None so the middleware reads the env.
    with TestClient(_build_app(threshold_ms=None)) as client:
        resp = client.get("/slow")
    assert resp.status_code == 200
    # 60ms < 5000ms threshold → no log.
    assert _log_records_with_event(caplog_logger, "request.slow") == []


def test_threshold_env_invalid_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A garbage env value must not crash the middleware — it
    falls back to ``DEFAULT_THRESHOLD_MS``. Catches a regression
    where a typo'd env var (``500ms`` instead of ``500``) would
    take down boot."""
    from app.observability.perf_logger import _resolve_threshold

    monkeypatch.setenv("PERF_SLOW_REQUEST_MS", "not-a-number")
    assert _resolve_threshold() == DEFAULT_THRESHOLD_MS


def test_threshold_env_clamps_to_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero / negative thresholds would log every request. The
    middleware clamps to 1 ms so misconfiguration can't accidentally
    DDoS the logging pipeline."""
    from app.observability.perf_logger import _resolve_threshold

    monkeypatch.setenv("PERF_SLOW_REQUEST_MS", "-50")
    assert _resolve_threshold() == 1.0


def test_user_id_field_hashed_when_present(
    caplog_logger: pytest.LogCaptureFixture,
) -> None:
    """When the auth dep has populated ``request.state.user``, the
    middleware logs the SALTED HASH of the user id — never the raw
    UUID. Regression-guard against PII leaking via logs."""
    import uuid

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    real_user_uuid = uuid.uuid4()

    class _FakeUser:
        id = real_user_uuid

    class _AttachUserMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
            request.state.user = _FakeUser()
            return await call_next(request)

    app = _build_app(threshold_ms=20.0)
    # Wrap so the user is attached BEFORE perf_logger sees the
    # request. ``add_middleware`` order: last-added is outermost.
    app.add_middleware(_AttachUserMiddleware)

    with TestClient(app) as client:
        resp = client.get("/slow")
    assert resp.status_code == 200
    records = _log_records_with_event(caplog_logger, "request.slow")
    assert len(records) == 1
    msg = records[0].getMessage()
    # The raw UUID must NOT appear anywhere in the log line.
    assert str(real_user_uuid) not in msg, (
        "Raw user UUID leaked into slow-request log — PII regression."
    )
    # The hashed field must be present.
    assert "user_id_hash" in msg


def test_anonymous_request_logs_with_null_user(
    caplog_logger: pytest.LogCaptureFixture,
) -> None:
    """Public routes (no auth dep) won't have ``state.user`` set —
    the middleware must handle that without raising."""
    with TestClient(_build_app(threshold_ms=20.0)) as client:
        resp = client.get("/slow")
    assert resp.status_code == 200
    # No exception in the middleware; one log line emitted.
    assert len(_log_records_with_event(caplog_logger, "request.slow")) == 1
