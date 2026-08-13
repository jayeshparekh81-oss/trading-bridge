"""Tape velocity (Module R3) — the founder's signal, from recorded timestamps only.

Per bar: its duration, a rolling baseline = median of the last M bar durations,
an acceleration ratio = duration / baseline, and a spike flag when the ratio drops
below a threshold (a SHORTER bar = a FASTER tape = ratio < 1). Needs >= M prior
bars before a baseline exists (ratio None, no spike until then).
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class Velocity:
    duration_s: float
    baseline_s: Optional[float]
    ratio: Optional[float]
    spike: bool


class TapeVelocity:
    """One per instrument."""

    def __init__(self, baseline_bars: int = 20, spike_ratio: float = 0.5):
        self.baseline_bars = max(1, int(baseline_bars))
        self.spike_ratio = float(spike_ratio)
        self._durations: deque[float] = deque(maxlen=self.baseline_bars)

    def on_bar_duration(self, duration_s: float) -> Velocity:
        # baseline from PRIOR bars (exclude the current one) for a causal signal
        baseline = (statistics.median(self._durations)
                    if len(self._durations) >= self.baseline_bars else None)
        ratio = (duration_s / baseline) if baseline and baseline > 0 else None
        spike = ratio is not None and ratio < self.spike_ratio
        self._durations.append(duration_s)
        return Velocity(duration_s=duration_s, baseline_s=baseline, ratio=ratio, spike=spike)
