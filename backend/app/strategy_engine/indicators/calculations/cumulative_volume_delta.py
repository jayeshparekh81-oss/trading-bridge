"""Cumulative Volume Delta (CVD) — proxy from candle close-vs-open.

Real CVD requires bid/ask trade tape — a microstructure feed
TRADETRI doesn't have at the bar-data layer. This implementation
is the *proxy* used widely on retail platforms: each bar's volume
is signed positive (bullish bar, ``close >= open``) or negative
(bearish bar, ``close < open``), then accumulated.

Definition::

    sign[i]  = +1 if close[i] >= open[i] else -1
    delta[i] = sign[i] * volume[i]
    CVD[i]   = CVD[i - 1] + delta[i]                         (CVD[0] = delta[0])

Cumulative — no parameters, no warm-up gap.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Doji bar (close == open) treated as bullish (matches Pine
      convention for ``close >= open``).
"""

from __future__ import annotations

from collections.abc import Sequence


def cumulative_volume_delta(
    opens: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> list[float | None]:
    """CVD proxy — cumulative signed volume."""
    n = len(opens)
    if n != len(closes) or n != len(volumes):
        raise ValueError(
            f"opens, closes, volumes must have the same length; "
            f"got {n}, {len(closes)}, {len(volumes)}."
        )
    if n == 0:
        return []
    out: list[float | None] = [0.0] * n
    running = 0.0
    for i in range(n):
        sign = 1.0 if closes[i] >= opens[i] else -1.0
        running += sign * volumes[i]
        out[i] = running
    return out


__all__ = ["cumulative_volume_delta"]
