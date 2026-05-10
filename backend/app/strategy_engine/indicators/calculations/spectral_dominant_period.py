"""Spectral Dominant Period - FFT-based dominant cycle estimate.

Distinct from Pack 11's :mod:`dominant_cycle_period` (which uses
the Hilbert Transform Discriminator). This module estimates the
dominant cycle by taking the discrete Fourier transform (DFT) of
the trailing window's de-trended close and emitting the period
of the bin with the largest magnitude.

Both indicators answer "what's the dominant cycle right now?"
but via different mechanisms; results will differ in the
shoulders of cycle transitions. Useful as a cross-check on
Hilbert-based estimates.

Implementation note: pure-Python DFT, O(N^2). For the default
window of 64 that's 4096 multiplications per bar — slow vs a
real FFT but acceptable at retail bar counts (no numpy
dependency). For windows > 256 consider migrating to numpy /
scipy in a Phase-2 wiring.

Definition::

    detrended[k] = close[k] - mean(window)
    X[f] = sum(detrended[k] * exp(-2*pi*i*f*k/N)) for k in 0..N-1
    period[f] = N / f                                 (skip f = 0)
    dominant_period = N / argmax(|X[f]|^2 for f in 1..N//2)

Default ``window = 64``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``window < 8`` rejected (FFT under-resolved).
    * ``window > n`` -> ``[]``.
    * Constant window (zero spectral energy) -> ``None``.
"""

from __future__ import annotations

import cmath
import math
from collections.abc import Sequence


def spectral_dominant_period(
    closes: Sequence[float], window: int = 64,
) -> list[float | None]:
    """Per-bar dominant cycle period via DFT."""
    if not isinstance(window, int) or isinstance(window, bool) or window < 8:
        raise ValueError(f"window must be an int >= 8; got {window!r}.")
    n = len(closes)
    if n == 0 or window > n:
        return []

    out: list[float | None] = [None] * n
    half = window // 2
    # Pre-compute the twiddle factors once: e^(-2*pi*i*f*k/window)
    # for f in 1..half-1 and k in 0..window-1.
    twiddles: list[list[complex]] = [
        [
            cmath.exp(-2j * math.pi * f * k / window)
            for k in range(window)
        ]
        for f in range(1, half)
    ]

    for i in range(window - 1, n):
        bar_window = closes[i - window + 1 : i + 1]
        mean_w = sum(bar_window) / window
        detrended = [c - mean_w for c in bar_window]
        # Skip the DC bin (f=0). Bins above N/2 are mirror images
        # — ignore them.
        magnitudes: list[float] = []
        for twid in twiddles:
            x_f = sum(detrended[k] * twid[k] for k in range(window))
            magnitudes.append(abs(x_f) ** 2)
        if not magnitudes or all(m == 0 for m in magnitudes):
            continue
        peak_f_idx = max(range(len(magnitudes)), key=lambda k: magnitudes[k])
        # f_idx 0 corresponds to f = 1, etc. (we start the
        # twiddles at f=1).
        f = peak_f_idx + 1
        out[i] = window / f
    return out


__all__ = ["spectral_dominant_period"]
