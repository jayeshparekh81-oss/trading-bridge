"""Cumulative Volume Delta (Module R3).

CVD is accumulated per CLASSIFIED TRADE (running += side*size), so it is canonical
and independent of bar type — feeding both the tick-bar and volume-bar series from
the same trade stream never double-counts. Each bar records the running CVD
sampled at its close; the slope is measured over a window of that bar series (a
separate SlopeSeries per bar type). Pure + deterministic (no wall-clock).
"""

from __future__ import annotations

from collections import deque

from tape.trades import Trade


class CVD:
    """Per-instrument running cumulative volume delta."""

    def __init__(self) -> None:
        self.running = 0

    def on_trade(self, t: Trade) -> int:
        self.running += t.side * t.size
        return self.running


class SlopeSeries:
    """Per (instrument, bar_type): CVD change per bar over a rolling window."""

    def __init__(self, window_bars: int = 20):
        self.window = max(1, int(window_bars))
        self._hist: deque[int] = deque(maxlen=self.window + 1)

    def sample(self, cvd_value: int) -> float:
        """Record the CVD at a bar close and return the current slope."""
        self._hist.append(cvd_value)
        if len(self._hist) < 2:
            return 0.0
        return (self._hist[-1] - self._hist[0]) / (len(self._hist) - 1)
