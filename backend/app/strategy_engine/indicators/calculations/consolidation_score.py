"""Consolidation score — multi-bar tightness measure.

Per bar, computes how "tight" the trailing ``period`` window is
relative to the bar's average range. Output is in ``[0, 1]``:

    1.0  → very tight consolidation (window range ≈ avg bar range)
    0.0  → very wide / trending (window range >> avg bar range)

Definition::

    avg_range[i]    = mean(high - low over period)
    window_range[i] = max(high) - min(low) over period
    score[i]        = clip(avg_range / window_range, 0, 1)

Default ``period = 10``.

Output length equals input length. Indices ``0 .. period - 2``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Window with ``window_range == 0`` (all bars at same H/L) →
      ``1.0`` (perfect consolidation).
"""

from __future__ import annotations

from collections.abc import Sequence


def consolidation_score(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 10,
) -> list[float | None]:
    """Consolidation tightness over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window_h = highs[i - period + 1 : i + 1]
        window_l = lows[i - period + 1 : i + 1]
        avg_range = sum(h - low for h, low in zip(window_h, window_l, strict=True)) / period
        window_range = max(window_h) - min(window_l)
        if window_range == 0:
            out[i] = 1.0
            continue
        score = avg_range / window_range
        # Clamp to [0, 1] — avg_range can technically equal
        # window_range only when every bar shares the same H/L
        # extremes (handled above), so values are bounded above.
        out[i] = max(0.0, min(1.0, score))
    return out


__all__ = ["consolidation_score"]
