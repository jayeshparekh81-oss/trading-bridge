"""Gaussian Channel — John Ehlers 4-pole filter.

Locked variant per reference doc (DonovanWall's Pine Public Library
implementation):

    poles      = 4 (HARDCODED)
    period     = 144 (default)
    multiplier = 1.414 (≈ sqrt(2))
    source     = HLCC4 = (high + low + 2*close) / 4
    band basis = 4-pole-filtered True Range (NOT stdev)

Recursion:
    beta  = (1 - cos(2*pi/period)) / (sqrt(2) - 1)
    alpha = -beta + sqrt(beta**2 + 2*beta)
    filt[i] = alpha**4 * src[i]
            + 4 * (1-alpha)    * filt[i-1]
            - 6 * (1-alpha)**2 * filt[i-2]
            + 4 * (1-alpha)**3 * filt[i-3]
            -     (1-alpha)**4 * filt[i-4]

Initialise filt[0..3] = src[0..3] (carries the input directly through
the warm-up). The same recursion is applied independently to HLCC4
(line) and to TR (band width basis).

Output:
    line  = filt_src
    upper = filt_src + multiplier * filt_tr
    lower = filt_src - multiplier * filt_tr

True Range:
    TR[0]   = high[0] - low[0]
    TR[i]   = max(high[i] - low[i],
                  abs(high[i] - close[i-1]),
                  abs(low[i]  - close[i-1]))  for i >= 1

Output length equals input length; no None warm-up positions because
the initialisation carries through.

Property: constant series ⇒ filter preserves constant (the recursion
coefficients sum to 1, by binomial identity).

Source: John F. Ehlers; DonovanWall's "Gaussian Channel [DW]" on
TradingView Public Library.

Edge cases:
    * Empty / length-mismatch -> ([], [], [])
    * Fewer than 4 bars -> partial init; subsequent recursion skipped
    * Invalid period -> ValueError
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def gaussian_channel(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 144,
    multiplier: float = 1.414,
) -> tuple[list[float], list[float], list[float]]:
    """Ehlers' 4-pole Gaussian Channel — returns (line, upper, lower)."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be int >= 2; got {period!r}.")
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
        raise ValueError(f"multiplier must be numeric; got {multiplier!r}.")
    if multiplier < 0:
        raise ValueError(f"multiplier must be >= 0; got {multiplier}.")
    n = len(highs)
    if not (n == len(lows) == len(closes)):
        raise ValueError(
            f"highs, lows, closes must be same length; got "
            f"{n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return ([], [], [])

    h = [float(x) for x in highs]
    l = [float(x) for x in lows]
    c = [float(x) for x in closes]

    # HLCC4 source.
    src = [(h[i] + l[i] + 2.0 * c[i]) / 4.0 for i in range(n)]

    # True Range series.
    tr: list[float] = [h[0] - l[0]]
    for i in range(1, n):
        tr.append(
            max(
                h[i] - l[i],
                abs(h[i] - c[i - 1]),
                abs(l[i] - c[i - 1]),
            )
        )

    # Filter coefficients.
    beta = (1.0 - math.cos(2.0 * math.pi / period)) / (math.sqrt(2.0) - 1.0)
    alpha = -beta + math.sqrt(beta * beta + 2.0 * beta)
    a = alpha
    one_minus = 1.0 - alpha
    coeff_0 = a ** 4
    coeff_1 = 4.0 * one_minus
    coeff_2 = 6.0 * one_minus ** 2
    coeff_3 = 4.0 * one_minus ** 3
    coeff_4 = one_minus ** 4

    def _filt(series: list[float]) -> list[float]:
        m = len(series)
        out = [0.0] * m
        # Warm-up: copy through input for first up-to-4 bars
        for i in range(min(4, m)):
            out[i] = series[i]
        # Recursion from i=4 onward.
        for i in range(4, m):
            out[i] = (
                coeff_0 * series[i]
                + coeff_1 * out[i - 1]
                - coeff_2 * out[i - 2]
                + coeff_3 * out[i - 3]
                - coeff_4 * out[i - 4]
            )
        return out

    filt_src = _filt(src)
    filt_tr = _filt(tr)

    upper = [filt_src[i] + multiplier * filt_tr[i] for i in range(n)]
    lower = [filt_src[i] - multiplier * filt_tr[i] for i in range(n)]

    return (filt_src, upper, lower)


__all__ = ["gaussian_channel"]
