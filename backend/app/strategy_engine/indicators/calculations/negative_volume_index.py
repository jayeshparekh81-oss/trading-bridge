"""Negative Volume Index (NVI, Paul Dysart 1936; Norman Fosback 1976).

Definition::

    NVI[0] = 1000.0                                         # Fosback's seed
    NVI[i] = NVI[i - 1] + NVI[i - 1] * pct_change(close)    when volume[i] < volume[i - 1]
    NVI[i] = NVI[i - 1]                                     otherwise

NVI tracks price action only on volume-DOWN days — Fosback's
"Smart Money" view. Companion to PVI (the volume-up tracker)
which also ships in this pack.

Output length equals input length. Index 0 is always ``1000.0``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``close[i - 1] == 0`` -> contribution that bar is 0
      (avoids div-by-zero).
"""

from __future__ import annotations

from collections.abc import Sequence


def negative_volume_index(
    closes: Sequence[float],
    volumes: Sequence[float],
) -> list[float | None]:
    """Cumulative NVI — no parameters."""
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0:
        return []
    out: list[float | None] = [1000.0]
    for i in range(1, n):
        prev_nvi = out[i - 1]
        if prev_nvi is None:
            out.append(None)
            continue
        if volumes[i] < volumes[i - 1] and closes[i - 1] != 0:
            pct = (closes[i] - closes[i - 1]) / closes[i - 1]
            out.append(prev_nvi + prev_nvi * pct)
        else:
            out.append(prev_nvi)
    return out


__all__ = ["negative_volume_index"]
