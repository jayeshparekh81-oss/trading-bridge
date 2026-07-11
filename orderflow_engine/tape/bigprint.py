"""Big-print detector (Module R3).

Emits a BigPrintEvent when a single trade's notional (price * size) meets a
per-instrument-class threshold, and a cluster event when K such prints land
within T seconds. Threshold 0 => INERT (nothing fires) — the uncalibrated
default, so no output until real thresholds come from replay evidence.

NOTE: notional = price * size here (size = traded qty). The contract lot-size
multiplier for futures is folded into the (uncalibrated) per-class threshold —
it is a constant per class, so calibrating the threshold absorbs it. Documented
in TAPE_NOTES.md.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from tape.trades import Trade


@dataclass
class BigPrintEvent:
    ts_ns: int
    side: int
    notional: float
    price: float
    size: int
    is_cluster: bool = False
    cluster_count: int = 0


class BigPrintDetector:
    """One per instrument."""

    def __init__(self, notional_threshold: float, cluster_k: int, cluster_window_s: float):
        self.threshold = float(notional_threshold)
        self.cluster_k = int(cluster_k)
        self.cluster_window_ns = int(float(cluster_window_s) * 1e9)
        self._recent: deque[int] = deque()   # timestamps of recent big prints

    def on_trade(self, t: Trade) -> list[BigPrintEvent]:
        """Return 0..2 events: the big print itself and/or a cluster trigger."""
        if self.threshold <= 0 or t.notional < self.threshold:
            return []
        out = [BigPrintEvent(t.ts_ns, t.side, t.notional, t.price, t.size)]
        self._recent.append(t.ts_ns)
        while self._recent and t.ts_ns - self._recent[0] > self.cluster_window_ns:
            self._recent.popleft()
        if len(self._recent) >= self.cluster_k:
            out.append(BigPrintEvent(t.ts_ns, t.side, t.notional, t.price, t.size,
                                     is_cluster=True, cluster_count=len(self._recent)))
        return out
