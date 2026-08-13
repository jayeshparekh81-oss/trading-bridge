"""Heartbeat watchdog: detect per-instrument gaps > threshold during market hours.

Time is injected (``ts_ns``/``now_ns`` passed in) so the logic is deterministic
and unit-testable without sleeping. The caller (main loop) drives ``poll`` on a
short cadence and forwards packets via ``on_packet``.

A gap is *opened* when an instrument has been silent for longer than the
threshold, and *closed* when the next packet arrives (or at session end). Only a
closed gap carries a full (start, end, duration); opening one emits a WARN.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("recorder.watchdog")

NS_PER_S = 1_000_000_000


@dataclass
class GapEvent:
    security_id: int
    start_ns: int
    end_ns: int
    duration_s: float
    open_ended: bool = False  # True if closed by session end rather than a packet


@dataclass
class Watchdog:
    threshold_s: float = 3.0
    last_ts: dict = field(default_factory=dict)   # sid -> last packet ts_ns
    open_gaps: dict = field(default_factory=dict)  # sid -> gap_start_ns

    @property
    def threshold_ns(self) -> int:
        return int(self.threshold_s * NS_PER_S)

    def register(self, security_id: int, seed_ns: int) -> None:
        """Begin tracking an instrument; ``seed_ns`` = session-start clock so a
        silent-from-the-start instrument is detected."""
        self.last_ts.setdefault(security_id, seed_ns)

    def on_packet(self, security_id: int, ts_ns: int) -> Optional[GapEvent]:
        """Record a packet. If it closes an open gap, return the GapEvent."""
        gap = None
        if security_id in self.open_gaps:
            start = self.open_gaps.pop(security_id)
            gap = GapEvent(security_id, start, ts_ns, (ts_ns - start) / NS_PER_S)
            log.warning("gap resolved for %s: %.2fs", security_id, gap.duration_s)
        self.last_ts[security_id] = ts_ns
        return gap

    def poll(self, now_ns: int) -> list[int]:
        """Open gaps for any instrument silent > threshold. Returns the list of
        security_ids for which a gap was newly opened (for WARN logging)."""
        newly = []
        for sid, last in self.last_ts.items():
            if sid in self.open_gaps:
                continue
            if now_ns - last > self.threshold_ns:
                self.open_gaps[sid] = last
                newly.append(sid)
                log.warning("gap OPENED for %s: silent %.2fs", sid,
                            (now_ns - last) / NS_PER_S)
        return newly

    def close_all(self, end_ns: int) -> list[GapEvent]:
        """Close any still-open gaps at session end."""
        out = []
        for sid, start in list(self.open_gaps.items()):
            out.append(GapEvent(sid, start, end_ns, (end_ns - start) / NS_PER_S,
                                open_ended=True))
        self.open_gaps.clear()
        return out
