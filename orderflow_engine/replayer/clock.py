"""Replay pacing — as-fast-as-possible (default), real-time, or Nx.

Pacing only controls WHEN events are delivered, never their order or content, so
the emitted stream (and its G1 hash) is identical across all speeds. ``sleep`` is
injected so tests assert timing without actually sleeping.
"""

from __future__ import annotations

import time
from typing import Callable

NS_PER_S = 1_000_000_000


def parse_speed(spec: str | float | None) -> float | None:
    """'max'/None -> None (no pacing); '1x'/'10x'/'2.5x'/number -> multiplier."""
    if spec is None:
        return None
    if isinstance(spec, (int, float)):
        return float(spec) if spec > 0 else None
    s = str(spec).strip().lower()
    if s in ("max", "asap", "0", ""):
        return None
    if s.endswith("x"):
        s = s[:-1]
    try:
        mult = float(s)
    except ValueError as exc:
        raise ValueError(f"invalid speed {spec!r} (use max, 1x, 10x, ...)") from exc
    if mult <= 0:
        return None
    return mult


class Pacer:
    """Sleeps between events to reproduce inter-event gaps at the chosen speed."""

    def __init__(self, speed: str | float | None = "max",
                 sleep: Callable[[float], None] = time.sleep):
        self.multiplier = parse_speed(speed)   # None => as-fast-as-possible
        self._sleep = sleep
        self._prev_ts: int | None = None

    def wait(self, ts_ns: int) -> None:
        if self.multiplier is None:
            self._prev_ts = ts_ns
            return
        if self._prev_ts is not None and ts_ns > self._prev_ts:
            delay = (ts_ns - self._prev_ts) / NS_PER_S / self.multiplier
            if delay > 0:
                self._sleep(delay)
        self._prev_ts = ts_ns
