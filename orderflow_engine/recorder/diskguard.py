"""Disk guard: pre-session gate + in-session pause/resume watchdog.

Born from the 2026-07-09 incident where the disk hit 100% mid-session and the
writer failed every flush for the rest of the day. Two independent protections,
both pure + deterministic (free-space is injected, so unit-testable without a
real disk):

  * Pre-session (``plan_start``, checked at connect): decide whether to arm the
    FULL universe (core + options), record CORE-ONLY (indices/futures/equities,
    no options — the bulk of the bytes are option chains), or SKIP the session
    entirely with a CRITICAL event.

  * In-session (``runtime_check``, polled every N seconds): PAUSE all writes
    below ``min_free_gb_runtime`` and auto-RESUME once free recovers above
    ``disk_resume_gb`` (hysteresis prevents flapping at the threshold).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Callable

log = logging.getLogger("recorder.diskguard")


class StartMode(Enum):
    FULL = "full"            # core + options
    CORE_ONLY = "core_only"  # indices/futures/equities only, no option chains
    SKIP = "skip"            # not enough disk to record at all


class DiskGuard:
    def __init__(self, *, min_free_gb_start: float, min_free_gb_core_only: float,
                 min_free_gb_runtime: float, disk_resume_gb: float,
                 free_gb_fn: Callable[[], float]):
        self.start_gb = float(min_free_gb_start)
        self.core_only_gb = float(min_free_gb_core_only)
        self.runtime_gb = float(min_free_gb_runtime)
        self.resume_gb = float(disk_resume_gb)
        self._free_gb_fn = free_gb_fn
        self.paused = False
        # Hysteresis sanity: resume must sit above the pause floor, else the
        # guard could flap pause/resume on a single reading.
        if self.resume_gb <= self.runtime_gb:
            log.warning("disk_resume_gb (%.1f) <= min_free_gb_runtime (%.1f); "
                        "resume threshold raised to avoid flapping",
                        self.resume_gb, self.runtime_gb)
            self.resume_gb = self.runtime_gb + 1.0

    def free_gb(self) -> float:
        return float(self._free_gb_fn())

    def plan_start(self) -> StartMode:
        """Pre-session gate decision from current free space."""
        free = self.free_gb()
        if free >= self.start_gb:
            mode = StartMode.FULL
        elif free >= self.core_only_gb:
            mode = StartMode.CORE_ONLY
        else:
            mode = StartMode.SKIP
        log.info("disk guard pre-session: %.1f GB free -> %s "
                 "(start>=%.0f, core_only>=%.0f)", free, mode.value,
                 self.start_gb, self.core_only_gb)
        return mode

    def runtime_check(self) -> str | None:
        """Poll free space; return 'pause' on entering paused state, 'resume'
        on recovery, else None. Idempotent while state is unchanged."""
        free = self.free_gb()
        if not self.paused and free < self.runtime_gb:
            self.paused = True
            log.error("DISK GUARD: %.1f GB free < %.1f GB runtime floor -> "
                      "PAUSING writes (drop-mode)", free, self.runtime_gb)
            return "pause"
        if self.paused and free >= self.resume_gb:
            self.paused = False
            log.warning("DISK GUARD: %.1f GB free >= %.1f GB resume -> "
                        "RESUMING writes", free, self.resume_gb)
            return "resume"
        return None
