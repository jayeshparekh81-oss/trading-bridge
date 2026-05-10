"""Positive Volume Index (PVI, Norman Fosback variant of Paul Dysart's 1936 NVI).

Substitute for the spec's ``accumulation_distribution_index``,
which is the same indicator as Pack 6's already-active
``accumulation_distribution`` (A/D Line) — adding it under a
different id would be LOC without signal value.

PVI is the natural companion to NVI (both ship in this pack):
PVI tracks price action only on volume-up days; NVI tracks
price action only on volume-down days. The pair is used in
Fosback's 1976 "Smart Money / Dumb Money" framework — PVI
follows retail flow (high-volume days), NVI follows
institutional flow (low-volume days).

Definition::

    PVI[0] = 1000.0                                         # Fosback's seed
    PVI[i] = PVI[i - 1] + PVI[i - 1] * pct_change(close)    when volume[i] > volume[i - 1]
    PVI[i] = PVI[i - 1]                                     otherwise

Output length equals input length. Index 0 is always ``1000.0``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``close[i - 1] == 0`` -> contribution that bar is 0
      (avoids div-by-zero).
"""

from __future__ import annotations

from collections.abc import Sequence


def positive_volume_index(
    closes: Sequence[float],
    volumes: Sequence[float],
) -> list[float | None]:
    """Cumulative PVI — no parameters."""
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0:
        return []
    out: list[float | None] = [1000.0]
    for i in range(1, n):
        prev_pvi = out[i - 1]
        if prev_pvi is None:
            out.append(None)
            continue
        if volumes[i] > volumes[i - 1] and closes[i - 1] != 0:
            pct = (closes[i] - closes[i - 1]) / closes[i - 1]
            out.append(prev_pvi + prev_pvi * pct)
        else:
            out.append(prev_pvi)
    return out


__all__ = ["positive_volume_index"]
