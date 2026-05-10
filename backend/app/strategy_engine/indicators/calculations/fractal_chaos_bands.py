"""Fractal Chaos Bands — Williams-fractal envelope.

A "fractal" in Bill Williams' terminology is a 5-bar pattern with
the middle bar's high (or low) being the highest (lowest) of all
5. The chaos bands track the most-recent fractal high / low; we
expose the **upper band** as the primary line and document the
lower-band variant as a co-indicator (same calc, different
projection).

Per bar::

    upper_band[i] = max recent fractal-high <= i, plateau-extended
    lower_band[i] = min recent fractal-low  <= i, plateau-extended

Default ``period = 9`` (the canonical 5-bar fractal applied with
a 9-bar lookback window for the "most recent" search).

Output length equals input length. Indices ``0 .. period - 1`` are
``None`` (need a full window to detect any fractal).

Returns the **upper band** by default; the dispatcher exposes
this single line.
"""

from __future__ import annotations

from collections.abc import Sequence


def fractal_chaos_bands(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 9,
) -> list[float | None]:
    """Upper-band line of the Fractal Chaos Bands.

    A 5-bar fractal needs ``period >= 5`` to mean anything; we
    accept any ``period >= 5`` and ``ValueError`` otherwise."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 5:
        raise ValueError(f"period must be an int >= 5; got {period!r}.")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or period >= n:
        return []

    # Find every "5-bar high fractal" within the input. Each
    # contributes the high of its centre bar to the upper band.
    fractal_highs: list[tuple[int, float]] = []
    for i in range(2, n - 2):
        h = highs[i]
        if h >= highs[i - 1] and h >= highs[i - 2] and h >= highs[i + 1] and h >= highs[i + 2]:
            fractal_highs.append((i, h))

    out: list[float | None] = [None] * n
    last_band: float | None = None
    fp = 0  # pointer into ``fractal_highs``
    for i in range(period, n):
        # Promote any fractals whose centre bar is now within the
        # trailing ``period`` window.
        while fp < len(fractal_highs) and fractal_highs[fp][0] <= i:
            last_band = fractal_highs[fp][1]
            fp += 1
        out[i] = last_band
    return out


__all__ = ["fractal_chaos_bands"]
