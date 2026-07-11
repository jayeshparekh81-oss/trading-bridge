"""Session VWAP + volume-weighted SD bands (Module R4).

Running, per instrument, from classified trades (the SAME trade stream R3 uses for
CVD — one trade-extraction truth). VWAP = Σ(price·size) / Σ(size); the band width
is the VOLUME-WEIGHTED standard deviation of price around VWAP:

    Var = Σ(size·price²)/Σ(size) − VWAP²     (weighted second moment − mean²)

Bands are VWAP ± k·SD for each configured multiplier k (e.g. 1σ, 2σ). Pure +
deterministic (no wall-clock).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tape.trades import Trade


@dataclass
class VwapSnapshot:
    vwap: float
    std: float
    cum_volume: int
    bands: dict          # {"upper_1": x, "lower_1": y, "upper_2": ...}


class SessionVWAP:
    def __init__(self, band_multipliers: list[float] | None = None):
        self.bands = list(band_multipliers or [1.0, 2.0])
        self._pv = 0.0        # Σ price·size
        self._v = 0           # Σ size
        self._pv2 = 0.0       # Σ price²·size

    def on_trade(self, t: Trade) -> None:
        self._pv += t.price * t.size
        self._pv2 += t.price * t.price * t.size
        self._v += t.size

    @property
    def vwap(self) -> float | None:
        return (self._pv / self._v) if self._v else None

    @property
    def std(self) -> float:
        if self._v == 0:
            return 0.0
        var = self._pv2 / self._v - (self._pv / self._v) ** 2
        return math.sqrt(var) if var > 0 else 0.0

    def snapshot(self) -> VwapSnapshot | None:
        vw = self.vwap
        if vw is None:
            return None
        sd = self.std
        bands: dict = {}
        for k in self.bands:
            tag = str(int(k)) if float(k).is_integer() else str(k)
            bands[f"upper_{tag}"] = vw + k * sd
            bands[f"lower_{tag}"] = vw - k * sd
        return VwapSnapshot(vwap=vw, std=sd, cum_volume=self._v, bands=bands)
