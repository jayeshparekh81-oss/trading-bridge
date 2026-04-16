"""Structured logging via structlog.

Production emits one JSON object per line so log shippers (Vector, Fluent
Bit, CloudWatch) can index every field. Development emits a colorised
console renderer so humans can read the stack trace.

Context — ``broker_name``, ``user_id``, ``request_id``, ``latency_ms`` —
is added with :mod:`structlog.contextvars`, which makes it task-local so
async concurrency does not leak fields between requests.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from typing import Any, cast

import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    unbind_contextvars,
)
from structlog.stdlib import BoundLogger
from structlog.typing import EventDict, Processor

from app.core.config import Environment, LogLevel, get_settings

_configured = False


def _drop_color_message_key(
    _logger: object, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Strip ``color_message`` — uvicorn injects it; it duplicates ``event``."""
    event_dict.pop("color_message", None)
    return event_dict


def _build_processors(*, json_output: bool) -> list[Processor]:
    """Common processor chain. JSON renderer is the only env-specific bit."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _drop_color_message_key,
    ]
    if json_output:
        shared.append(structlog.processors.JSONRenderer())
    else:
        shared.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))
    return shared


def configure_logging(
    *,
    level: LogLevel | str | None = None,
    environment: Environment | str | None = None,
    force: bool = False,
) -> None:
    """Configure structlog and the stdlib root logger.

    Args:
        level: Override ``LOG_LEVEL`` from settings (test convenience).
        environment: Override ``ENVIRONMENT`` from settings.
        force: Re-run configuration even if already configured this process.

    Idempotent under normal use — structlog's ``configure`` is global, so
    we early-return after the first call to avoid clobbering test setup.
    """
    global _configured
    if _configured and not force:
        return

    settings = get_settings()
    resolved_level = LogLevel(level) if level else settings.log_level
    resolved_env = Environment(environment) if environment else settings.environment
    json_output = resolved_env in (Environment.PRODUCTION, Environment.STAGING)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, resolved_level.value),
        force=True,
    )

    structlog.configure(
        processors=_build_processors(json_output=json_output),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, resolved_level.value)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def reset_logging() -> None:
    """Test helper — drop the ``_configured`` latch so the next call rebuilds."""
    global _configured
    _configured = False
    structlog.reset_defaults()


def get_logger(name: str | None = None, **initial_context: Any) -> BoundLogger:
    """Return a structlog logger, ensuring configuration has run.

    Pass ``initial_context`` to bind static fields (typically
    ``broker_name=...``) on the returned logger.
    """
    if not _configured:
        configure_logging()
    logger = structlog.get_logger(name) if name else structlog.get_logger()
    if initial_context:
        logger = logger.bind(**initial_context)
    return cast(BoundLogger, logger)


def bind_request_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    broker_name: str | None = None,
    **extra: Any,
) -> None:
    """Bind common request-scoped fields into the contextvars store.

    Anything bound here flows into every log line emitted from the same
    asyncio task / stdlib thread until :func:`clear_request_context` runs.
    """
    fields: dict[str, Any] = {}
    if request_id is not None:
        fields["request_id"] = request_id
    if user_id is not None:
        fields["user_id"] = user_id
    if broker_name is not None:
        fields["broker_name"] = broker_name
    fields.update(extra)
    if fields:
        bind_contextvars(**fields)


def clear_request_context(*keys: str) -> None:
    """Drop specific keys (or everything if no keys given) from contextvars."""
    if keys:
        unbind_contextvars(*keys)
    else:
        clear_contextvars()


def context_snapshot() -> Mapping[str, Any]:
    """Read-only view of the current contextvars — handy in tests."""
    return dict(structlog.contextvars.get_contextvars())


__all__ = [
    "bind_request_context",
    "clear_request_context",
    "configure_logging",
    "context_snapshot",
    "get_logger",
    "reset_logging",
]
