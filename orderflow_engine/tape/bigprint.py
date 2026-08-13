"""Big-print detector (Module R3).

A single trade whose notional (price * size) is unusually large for THAT instrument is an
institutional footprint (a D1 metaorder leaking onto the tape). Two ways to decide "unusual":

  * FIXED mode (legacy): notional >= a per-class ₹ threshold. Threshold 0 => INERT.
  * PERCENTILE mode (2026-07-17): notional >= the Nth percentile of the instrument's OWN
    recent trade distribution — a rolling, per-instrument, self-calibrating cut. No hardcoded
    ₹ number (that would be the lot-size anti-pattern: a fixed cut fitted to 2-day data, and
    BANKNIFTY's p99 count swung 89->15 across those two days). Same lesson as OFI's floor+scale
    and the ATR-derived stop: derive the cut from the instrument's own live distribution.

PERCENTILE mode is:
  * STRICTLY NO-LOOK-AHEAD — the percentile at trade t uses ONLY trades BEFORE t (the window is
    appended to AFTER the check), so a huge print at t+1 cannot move the threshold at t.
  * GRADED, not binary — the event carries ``strength`` in [0,1] = where the print sits in the
    tail (its percentile-rank mapped from [percentile,100] -> [0,1]): a p99.9 print scores ~1,
    a print at exactly the p99 cut scores ~0. Same shape as OFI (0 at the floor, grades up).
  * WARM until history exists — below ``min_samples`` observed trades the percentile is not
    estimable, so the detector contributes NOTHING (no event). Not day-1 leaky self-data, not a
    fail: "0 until warm" is the only honest option (see TAPE_NOTES).

NOTE: notional = price * size (size = traded qty). The contract lot multiplier is a per-class
constant folded into the per-instrument distribution, so the percentile absorbs it.

PERF: in percentile mode the cut is recomputed from the rolling window each trade (O(N log N)).
That is fine for the tradeable futures; when ACTIVATED across the full instrument set, scope
percentile mode to the tradeables (or raise the recompute stride) — an activation-time concern,
gated separately. Default mode is 'fixed' with threshold 0 => this path never runs until armed.
"""

from __future__ import annotations

import math
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
    strength: float = 1.0          # [0,1] graded tail position (fixed mode = 1.0, binary)


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Nearest-rank percentile of an ASCENDING list (no interpolation)."""
    if not sorted_vals:
        return 0.0
    k = max(1, min(len(sorted_vals), math.ceil(p / 100.0 * len(sorted_vals))))
    return sorted_vals[k - 1]


class BigPrintDetector:
    """One per instrument (constructed in the tape engine's per-instrument state)."""

    def __init__(self, notional_threshold: float, cluster_k: int, cluster_window_s: float,
                 *, mode: str = "fixed", percentile: float = 99.0, lookback: int = 2000,
                 min_samples: int = 500):
        self.threshold = float(notional_threshold)
        self.cluster_k = int(cluster_k)
        self.cluster_window_ns = int(float(cluster_window_s) * 1e9)
        self._recent: deque[int] = deque()          # timestamps of recent big prints (cluster)
        # percentile-mode state (per instrument, rolling)
        self.mode = mode
        self.percentile = float(percentile)
        self.lookback = int(lookback)
        self.min_samples = int(min_samples)
        self._window: deque[float] = deque(maxlen=self.lookback)   # rolling notionals, prior trades

    def on_trade(self, t: Trade) -> list[BigPrintEvent]:
        """Return 0..2 events: the big print itself and/or a cluster trigger."""
        big, strength = self._classify(t)
        if not big:
            return []
        out = [BigPrintEvent(t.ts_ns, t.side, t.notional, t.price, t.size, strength=strength)]
        self._recent.append(t.ts_ns)
        while self._recent and t.ts_ns - self._recent[0] > self.cluster_window_ns:
            self._recent.popleft()
        if len(self._recent) >= self.cluster_k:
            out.append(BigPrintEvent(t.ts_ns, t.side, t.notional, t.price, t.size,
                                     is_cluster=True, cluster_count=len(self._recent),
                                     strength=strength))
        return out

    # -- classification --------------------------------------------------------
    def _classify(self, t: Trade) -> tuple[bool, float]:
        if self.mode == "percentile":
            return self._classify_percentile(t)
        # FIXED mode (legacy, binary): threshold 0 => INERT.
        if self.threshold <= 0 or t.notional < self.threshold:
            return False, 0.0
        return True, 1.0

    def _classify_percentile(self, t: Trade) -> tuple[bool, float]:
        w = self._window
        big, strength = False, 0.0
        if len(w) >= self.min_samples:                       # WARM (else contribute nothing)
            ordered = sorted(w)                              # window = PRIOR trades only
            cut = _percentile(ordered, self.percentile)      # NO-LOOK-AHEAD: t not yet appended
            if cut > 0 and t.notional >= cut:
                big = True
                strength = self._strength(ordered, t.notional)
        w.append(t.notional)                                 # append AFTER the check
        return big, strength

    def _strength(self, ordered: list[float], notional: float) -> float:
        """GRADED tail position in [0,1]: the print's percentile-rank mapped from
        [percentile, 100] -> [0, 1]. A print at the cut -> ~0; the tail extreme -> ~1."""
        below = 0
        for x in ordered:                                    # ordered ascending
            if x < notional:
                below += 1
            else:
                break
        rank_pct = 100.0 * below / len(ordered)
        p = self.percentile
        return 1.0 if p >= 100.0 else _clamp01((rank_pct - p) / (100.0 - p))
