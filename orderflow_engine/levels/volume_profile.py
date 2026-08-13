"""Developing intraday volume profile (Module R4).

Histogram of traded volume by price bin (bin_size knob), from the same classified
trade stream as VWAP/CVD. Computes:
  * POC  — price bin with the most volume
  * VAH/VAL — bounds of the value area: the smallest contiguous band of bins around
    the POC holding >= value_area_pct of total volume (expanded one bin at a time
    toward the heavier neighbour; deterministic)
  * HVN/LVN — high/low-volume-node flags. These are SIGNAL flags, so they ship
    INERT (threshold 0 => no flags) per doctrine, until calibrated from the
    replayed volume-per-bin distribution.

Bins are keyed by their lower edge: bin(price) = floor(price / bin_size) * bin_size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from tape.trades import Trade


@dataclass
class ProfileResult:
    bin_size: float
    total_volume: int
    poc: float | None
    vah: float | None
    val: float | None
    bins: dict = field(default_factory=dict)   # bin_low -> volume
    hvn: list = field(default_factory=list)
    lvn: list = field(default_factory=list)


class VolumeProfile:
    def __init__(self, bin_size: float):
        self.bin_size = float(bin_size)
        self.bins: dict[float, int] = {}

    def _bin(self, price: float) -> float:
        return math.floor(price / self.bin_size) * self.bin_size

    def on_trade(self, t: Trade) -> None:
        b = round(self._bin(t.price), 6)
        self.bins[b] = self.bins.get(b, 0) + t.size

    def result(self, value_area_pct: float = 0.70,
               hvn_threshold: float = 0, lvn_threshold: float = 0) -> ProfileResult:
        total = sum(self.bins.values())
        if not self.bins or total == 0:
            return ProfileResult(self.bin_size, 0, None, None, None, dict(self.bins))
        # ordered by price
        prices = sorted(self.bins)
        vols = [self.bins[p] for p in prices]
        poc_idx = max(range(len(prices)), key=lambda i: (vols[i], -prices[i]))
        poc = prices[poc_idx]

        # value area: expand from POC toward the heavier neighbour until >= target
        target = total * value_area_pct
        lo = hi = poc_idx
        acc = vols[poc_idx]
        while acc < target and (lo > 0 or hi < len(prices) - 1):
            up = vols[hi + 1] if hi < len(prices) - 1 else -1
            dn = vols[lo - 1] if lo > 0 else -1
            if up >= dn:
                hi += 1
                acc += vols[hi]
            else:
                lo -= 1
                acc += vols[lo]
        val, vah = prices[lo], prices[hi]

        hvn = sorted(p for p in prices if hvn_threshold > 0 and self.bins[p] >= hvn_threshold)
        lvn = sorted(p for p in prices if lvn_threshold > 0 and self.bins[p] <= lvn_threshold)
        return ProfileResult(self.bin_size, total, poc, vah, val, dict(self.bins), hvn, lvn)
