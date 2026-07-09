"""Rate-limited logging helper.

The 2026-07-09 disk-full incident turned a per-flush writer exception into
thousands of full tracebacks (every 5s flush, for hours), which itself consumed
disk + log space. :class:`ThrottledLogger` emits at most ONE full record per
``interval_s`` per key; further hits within the window are counted and folded
into the next emitted record's suffix (``+N suppressed in last Ns``).

Time is injected (``clock``) so the throttle is deterministic and unit-testable
without sleeping.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

log = logging.getLogger("recorder.ratelimit")


class ThrottledLogger:
    def __init__(self, logger: logging.Logger, interval_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        self._log = logger
        self.interval_s = float(interval_s)
        self._clock = clock
        self._last_emit: dict[str, float] = {}
        self._suppressed: dict[str, int] = {}

    def _should_emit(self, key: str) -> bool:
        now = self._clock()
        last = self._last_emit.get(key)
        if last is None or (now - last) >= self.interval_s:
            self._last_emit[key] = now
            return True
        self._suppressed[key] = self._suppressed.get(key, 0) + 1
        return False

    def _suffix(self, key: str) -> str:
        n = self._suppressed.pop(key, 0)
        if n:
            return f" (+{n} suppressed in last {self.interval_s:.0f}s)"
        return ""

    def exception(self, key: str, msg: str, *args) -> None:
        """Log a full traceback (call inside an ``except`` block), throttled."""
        if self._should_emit(key):
            self._log.exception(msg + self._suffix(key), *args)

    def error(self, key: str, msg: str, *args) -> None:
        if self._should_emit(key):
            self._log.error(msg + self._suffix(key), *args)

    def warning(self, key: str, msg: str, *args) -> None:
        if self._should_emit(key):
            self._log.warning(msg + self._suffix(key), *args)

    def suppressed_count(self, key: str) -> int:
        """Currently-buffered suppressed count for ``key`` (for tests/metrics)."""
        return self._suppressed.get(key, 0)
