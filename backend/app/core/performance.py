"""Latency tracking — the Speed layer.

Two interfaces, both of which emit the same structured log line and
forward to a pluggable observer (Prometheus collector, OTel exporter):

    * :class:`LatencyTimer` — context manager for arbitrary code blocks.
    * :func:`track_latency`  — decorator for async (and sync) functions.

The observer hook is intentionally kept as a global callable so the
metrics module (added in a later step) can register itself once at startup
without every call-site importing ``prometheus_client`` directly.
"""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from types import TracebackType
from typing import Any, ParamSpec, TypeVar

from app.core.logging import get_logger

_P = ParamSpec("_P")
_R = TypeVar("_R")

_logger = get_logger("performance")

#: Pluggable observer — receives ``(operation, latency_ms, success, tags)``.
#: The metrics layer registers a Prometheus histogram here at startup;
#: until then it stays as a no-op so the decorator carries zero overhead.
_LatencyObserver = Callable[[str, float, bool, dict[str, Any]], None]
_observer: _LatencyObserver | None = None

#: Allows nested timers to inherit tags from an enclosing scope.
_active_tags: ContextVar[dict[str, Any]] = ContextVar(
    "_latency_active_tags", default={}
)


def register_latency_observer(observer: _LatencyObserver | None) -> None:
    """Install (or clear with ``None``) the observer that receives every sample.

    Called by the metrics bootstrap. Replacing the observer is allowed —
    useful in tests that want to assert on emitted samples.
    """
    global _observer
    _observer = observer


def get_latency_observer() -> _LatencyObserver | None:
    return _observer


class LatencyTimer:
    """Context manager that times the wrapped block and emits a sample.

    Example:
        >>> with LatencyTimer("db.query", tags={"table": "orders"}) as t:
        ...     fetch_orders()
        >>> t.latency_ms
        12.4
    """

    __slots__ = ("operation", "tags", "_start", "latency_ms", "success")

    def __init__(self, operation: str, tags: dict[str, Any] | None = None) -> None:
        self.operation = operation
        self.tags: dict[str, Any] = dict(_active_tags.get())
        if tags:
            self.tags.update(tags)
        self._start: float = 0.0
        self.latency_ms: float = 0.0
        self.success: bool = True

    def __enter__(self) -> LatencyTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.latency_ms = (time.perf_counter() - self._start) * 1000.0
        self.success = exc_type is None
        _emit(self.operation, self.latency_ms, self.success, self.tags)


def _emit(
    operation: str, latency_ms: float, success: bool, tags: dict[str, Any]
) -> None:
    """Log + forward to the observer. Never let an observer error escape."""
    log = _logger.bind(operation=operation, latency_ms=round(latency_ms, 3), **tags)
    if success:
        log.debug("latency.sample", success=True)
    else:
        log.warning("latency.sample", success=False)
    if _observer is not None:
        try:
            _observer(operation, latency_ms, success, tags)
        except Exception as exc:  # noqa: BLE001 — observer failure must not break callers
            _logger.warning(
                "latency.observer_failed",
                operation=operation,
                error=str(exc),
            )


def track_latency(
    operation: str | None = None,
    *,
    tags: dict[str, Any] | None = None,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Decorator that records execution latency in milliseconds.

    Works on both sync and async callables — async usage is the common
    case for broker calls. ``operation`` defaults to ``"<module>.<name>"``
    when omitted.

    The wrapper resolves whether the target is async at decoration time
    (via :func:`asyncio.iscoroutinefunction`), so each call pays only the
    cost of one function dispatch — no per-call ``await`` introspection.
    """
    static_tags = dict(tags) if tags else {}

    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        op_name = operation or f"{func.__module__}.{func.__qualname__}"

        if inspect.iscoroutinefunction(func):
            async_func: Callable[_P, Awaitable[Any]] = func  # type: ignore[assignment]

            @functools.wraps(func)
            async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Any:
                start = time.perf_counter()
                success = True
                try:
                    return await async_func(*args, **kwargs)
                except BaseException:
                    success = False
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    _emit(op_name, latency_ms, success, static_tags)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            start = time.perf_counter()
            success = True
            try:
                return func(*args, **kwargs)
            except BaseException:
                success = False
                raise
            finally:
                latency_ms = (time.perf_counter() - start) * 1000.0
                _emit(op_name, latency_ms, success, static_tags)

        return sync_wrapper

    return decorator


__all__ = [
    "LatencyTimer",
    "get_latency_observer",
    "register_latency_observer",
    "track_latency",
]
