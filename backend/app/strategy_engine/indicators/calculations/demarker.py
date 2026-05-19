"""DeMarker (DeM) — Tom DeMark's bounded overbought/oversold oscillator.

DeMark's approach (1990s) compares per-bar high/low extension magnitudes.
The smoothed ratio of "new-high" pressure vs total "new-high + new-low"
pressure produces a 0..1 oscillator. >0.7 typically reads overbought;
<0.3 reads oversold.

Definition::

    DeMax[i] = max(0, high[i] - high[i - 1])      (zero for i = 0)
    DeMin[i] = max(0, low[i - 1] - low[i])        (zero for i = 0)

    SmoothedDeMax[i] = SMA(DeMax, period)[i]
    SmoothedDeMin[i] = SMA(DeMin, period)[i]

    denom = SmoothedDeMax + SmoothedDeMin
    DeMarker[i] = SmoothedDeMax / denom           (None if denom == 0)

    Default ``period = 14`` (DeMark's recommended).
    First defined index is ``period`` (one extra warm-up bar because
    DeMax/DeMin are undefined at i=0).

Edge cases per Phase 1 contract:
    * Empty / length-mismatch -> ``[]`` / ``ValueError``
    * ``period > n - 1`` -> ``[]``
    * Flat series ⇒ DeMax + DeMin = 0 ⇒ DeMarker is ``None`` for that bar

Source: Tom DeMark, "The New Science of Technical Analysis" (1994);
standard Pine community implementation.
"""

from __future__ import annotations

from collections.abc import Sequence


def demarker(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Tom DeMark's DeMarker oscillator (bounded 0..1)."""
    _check_period(period)
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have same length; got {n}, {len(lows)}."
        )
    if n == 0 or period > n - 1:
        # Need at least period + 1 bars (one extra for the diff seed at i=0).
        return []

    # Build DeMax / DeMin series. Index 0 is 0 by convention (no prior bar).
    demax: list[float] = [0.0]
    demin: list[float] = [0.0]
    for i in range(1, n):
        demax.append(max(0.0, highs[i] - highs[i - 1]))
        demin.append(max(0.0, lows[i - 1] - lows[i]))

    out: list[float | None] = [None] * n
    # First valid SMA window for period N uses indices [1 .. period].
    # That's the first window that covers all DEFINED DeMax/DeMin values.
    # SmoothedDeMax[period] = sum(demax[1..period]) / period
    for i in range(period, n):
        win_demax = sum(demax[i - period + 1 : i + 1]) / period
        win_demin = sum(demin[i - period + 1 : i + 1]) / period
        denom = win_demax + win_demin
        if denom == 0.0:
            out[i] = None
        else:
            out[i] = win_demax / denom
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["demarker"]
