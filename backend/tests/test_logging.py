"""Unit tests for :mod:`app.core.logging`."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest
import structlog

from app.core import logging as core_logging
from app.core.config import Environment, LogLevel


@pytest.fixture(autouse=True)
def _isolated_logging() -> Iterator[None]:
    core_logging.reset_logging()
    structlog.contextvars.clear_contextvars()
    yield
    core_logging.reset_logging()
    structlog.contextvars.clear_contextvars()


class TestConfigure:
    def test_configure_idempotent(self) -> None:
        core_logging.configure_logging(
            level=LogLevel.INFO, environment=Environment.DEVELOPMENT
        )
        first = structlog.get_config()
        core_logging.configure_logging(
            level=LogLevel.WARNING, environment=Environment.PRODUCTION
        )
        # Second call is a no-op without force=True.
        assert structlog.get_config() == first

    def test_force_reconfigures(self) -> None:
        core_logging.configure_logging(
            level=LogLevel.INFO, environment=Environment.DEVELOPMENT
        )
        first = structlog.get_config()
        core_logging.configure_logging(
            level=LogLevel.WARNING, environment=Environment.PRODUCTION, force=True
        )
        assert structlog.get_config() != first

    def test_production_emits_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        core_logging.configure_logging(
            level=LogLevel.INFO, environment=Environment.PRODUCTION, force=True
        )
        log = core_logging.get_logger("test")
        log.info("hello", broker_name="fyers", latency_ms=12.5)
        captured = capsys.readouterr().err.strip()
        # Last line is ours; uvicorn isn't running here.
        line = captured.splitlines()[-1]
        payload = json.loads(line)
        assert payload["event"] == "hello"
        assert payload["broker_name"] == "fyers"
        assert payload["latency_ms"] == 12.5
        assert payload["level"] == "info"
        assert "timestamp" in payload

    def test_development_emits_console(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        core_logging.configure_logging(
            level=LogLevel.INFO, environment=Environment.DEVELOPMENT, force=True
        )
        log = core_logging.get_logger("test")
        log.info("dev-event", foo="bar")
        captured = capsys.readouterr().err
        assert "dev-event" in captured
        # Console renderer never produces a JSON object on its own line.
        with pytest.raises(json.JSONDecodeError):
            json.loads(captured.strip().splitlines()[-1])


class TestContext:
    def test_bind_request_context_flows_into_logs(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        core_logging.configure_logging(
            level=LogLevel.INFO, environment=Environment.PRODUCTION, force=True
        )
        core_logging.bind_request_context(
            request_id="req-1", user_id="user-1", broker_name="fyers"
        )
        core_logging.get_logger("svc").info("place_order")
        line = capsys.readouterr().err.strip().splitlines()[-1]
        payload = json.loads(line)
        assert payload["request_id"] == "req-1"
        assert payload["user_id"] == "user-1"
        assert payload["broker_name"] == "fyers"

    def test_bind_request_context_extra_kwargs(self) -> None:
        core_logging.bind_request_context(strategy="straddle")
        snap = core_logging.context_snapshot()
        assert snap["strategy"] == "straddle"

    def test_clear_specific_keys(self) -> None:
        core_logging.bind_request_context(request_id="r", user_id="u")
        core_logging.clear_request_context("user_id")
        snap = core_logging.context_snapshot()
        assert snap == {"request_id": "r"}

    def test_clear_all(self) -> None:
        core_logging.bind_request_context(request_id="r", user_id="u")
        core_logging.clear_request_context()
        assert core_logging.context_snapshot() == {}

    def test_get_logger_auto_configures(self) -> None:
        # Pre-condition: we just reset_logging in the fixture.
        log = core_logging.get_logger("auto", broker_name="fyers")
        assert log is not None
        # Configuration must have happened as a side effect.
        assert structlog.is_configured()

    def test_get_logger_without_initial_context(self) -> None:
        log = core_logging.get_logger()
        assert log is not None

    def test_color_message_dropped(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        core_logging.configure_logging(
            level=LogLevel.INFO, environment=Environment.PRODUCTION, force=True
        )
        # Simulate uvicorn injecting `color_message`.
        core_logging.get_logger("u").info("startup", color_message="bright")
        line = capsys.readouterr().err.strip().splitlines()[-1]
        payload = json.loads(line)
        assert "color_message" not in payload

    def test_log_level_filters_out_debug(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        core_logging.configure_logging(
            level=LogLevel.WARNING, environment=Environment.PRODUCTION, force=True
        )
        log = core_logging.get_logger("flt")
        log.debug("nope")
        log.warning("yep")
        out = capsys.readouterr().err.strip()
        assert "yep" in out
        assert "nope" not in out
