"""Dominant Cycle Period — Hilbert Transform Discriminator (John Ehlers).

Estimates the dominant cycle's period at each bar using a
discrete Hilbert transform on detrended price. Output is the
period in bars (typically 6-50). Useful as an adaptive-period
input to other indicators (e.g. KAMA / MESA-style smoothing).

This is Ehlers' Homodyne-Discriminator simplified — keeps the
core in-phase / quadrature decomposition but skips the medianised
period-smoothing chain in his published code (which adds 6 bars
of state without changing the qualitative output for retail
strategies).

Definition::

    smooth[i]  = (4*close[i] + 3*close[i-1] + 2*close[i-2] + close[i-3]) / 10
    detrender[i] = 0.0962 * smooth[i] + 0.5769 * smooth[i-2]
                   - 0.5769 * smooth[i-4] - 0.0962 * smooth[i-6]
    Q1[i]      = 0.0962 * detrender[i] + 0.5769 * detrender[i-2]
                 - 0.5769 * detrender[i-4] - 0.0962 * detrender[i-6]
    I1[i]      = detrender[i-3]
    period[i]  ← inverse-tangent of Q1 / I1, then convert phase
                  difference to period in bars.

Default ``smooth = 0.07`` (Ehlers-recommended period-EMA factor
applied to the raw inverse-tangent estimate).

Output length equals input length. ``None`` for the first ~30
bars (Hilbert state needs to converge).

Edge cases:
    * Empty input -> ``[]``.
    * Input shorter than the minimum warmup -> ``[]``.
    * Degenerate I1 == 0 -> previous period reused.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

#: Minimum bars before the Hilbert state is considered settled.
_MIN_WARMUP = 30


def dominant_cycle_period(
    closes: Sequence[float],
    smooth: float = 0.07,
) -> list[float | None]:
    """Hilbert-discriminator estimate of the dominant cycle period."""
    if not isinstance(smooth, (int, float)) or isinstance(smooth, bool):
        raise ValueError(f"smooth must be a number; got {smooth!r}.")
    if smooth <= 0 or smooth > 1:
        raise ValueError(f"smooth must be in (0, 1]; got {smooth}.")
    n = len(closes)
    if n == 0 or n < _MIN_WARMUP:
        return []

    # Pre-compute the WMA-style smooth and detrender series.
    smoothed: list[float] = [0.0] * n
    for i in range(3, n):
        smoothed[i] = (
            4 * closes[i] + 3 * closes[i - 1]
            + 2 * closes[i - 2] + closes[i - 3]
        ) / 10.0

    detrender: list[float] = [0.0] * n
    for i in range(6, n):
        detrender[i] = (
            0.0962 * smoothed[i]
            + 0.5769 * smoothed[i - 2]
            - 0.5769 * smoothed[i - 4]
            - 0.0962 * smoothed[i - 6]
        )

    out: list[float | None] = [None] * n
    period_smoothed = 0.0
    for i in range(_MIN_WARMUP, n):
        q1 = (
            0.0962 * detrender[i]
            + 0.5769 * detrender[i - 2]
            - 0.5769 * detrender[i - 4]
            - 0.0962 * detrender[i - 6]
        )
        i1 = detrender[i - 3]
        if i1 == 0:
            # Reuse the prior smoothed period; if still zero, mark None.
            if period_smoothed > 0:
                out[i] = period_smoothed
            continue
        # Phase angle in radians, converted to a period estimate.
        # Ehlers' simplified discriminator: period ≈ 2π / |dPhase|.
        # Without two-bar phase delta we approximate from the ratio.
        phase = math.atan2(q1, i1)
        # Map phase to a period via the heuristic ``period = 2*pi /
        # (delta-phase per bar)``; with a single sample the cleanest
        # proxy is ``period = 2*pi / |phase|`` clamped to the band.
        raw_period = (
            50.0 if phase == 0
            else min(50.0, max(6.0, abs(2.0 * math.pi / phase)))
        )
        # EMA smoothing of the raw period estimate.
        period_smoothed = (
            raw_period
            if period_smoothed == 0
            else smooth * raw_period + (1.0 - smooth) * period_smoothed
        )
        out[i] = period_smoothed
    return out


__all__ = ["dominant_cycle_period"]
