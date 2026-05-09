"""Underwater Curve — drawdown from running all-time peak.

Cumulative (NOT windowed) — the running peak is taken over every
bar from the start of the input series. Output is ``<= 0`` at every
bar, expressed as a percent:

    peak[i]           = max(closes[0..i])
    underwater[i]     = (close[i] - peak[i]) / peak[i] * 100

A reading of ``0.0`` means the bar made a new all-time high; a
reading of ``-12.5`` means the equity is 12.5 % below its peak.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``close <= 0`` at the running peak -> ``None`` from that bar
      until a positive close re-seeds the peak.
"""

from __future__ import annotations

from collections.abc import Sequence


def underwater_curve(closes: Sequence[float]) -> list[float | None]:
    """Underwater curve from the running all-time high."""
    n = len(closes)
    if n == 0:
        return []

    out: list[float | None] = [None] * n
    peak: float | None = None
    for i in range(n):
        c = closes[i]
        if peak is None or c > peak:
            peak = c
        if peak is None or peak <= 0:
            continue
        out[i] = (c - peak) / peak * 100.0
    return out


__all__ = ["underwater_curve"]
