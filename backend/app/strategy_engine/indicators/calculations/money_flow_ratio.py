"""Money Flow Ratio — up-money / down-money over a rolling window.

Underpins the existing :mod:`mfi` (Money Flow Index, which maps
this ratio to a 0-100 oscillator). Exposed here as the raw
ratio so strategies can branch on it directly without the MFI
normalisation.

Definition::

    typical[i] = (high + low + close) / 3
    raw[i]     = typical[i] * volume[i]
    pos[i]     = raw[i] if typical[i] > typical[i - 1] else 0
    neg[i]     = raw[i] if typical[i] < typical[i - 1] else 0
    MFR[i]     = sum(pos over period) / sum(neg over period)

Default ``period = 14``.

Output length equals input length. Indices ``0 .. period - 1``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n`` -> ``[]``.
    * Window with zero down-money -> ratio is undefined; we
      return a large sentinel ``float("inf")`` so the caller can
      branch. (MFI uses this case to clamp to 100; the raw
      ratio doesn't have a natural upper bound.)
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def money_flow_ratio(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Money Flow Ratio over a rolling ``period`` window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            f"highs, lows, closes, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or period >= n:
        return []

    typical = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]
    raw = [typical[i] * volumes[i] for i in range(n)]
    pos = [0.0] * n
    neg = [0.0] * n
    for i in range(1, n):
        if typical[i] > typical[i - 1]:
            pos[i] = raw[i]
        elif typical[i] < typical[i - 1]:
            neg[i] = raw[i]

    out: list[float | None] = [None] * n
    for i in range(period, n):
        pos_sum = sum(pos[i - period + 1 : i + 1])
        neg_sum = sum(neg[i - period + 1 : i + 1])
        if neg_sum == 0:
            out[i] = math.inf if pos_sum > 0 else 0.0
        else:
            out[i] = pos_sum / neg_sum
    return out


__all__ = ["money_flow_ratio"]
