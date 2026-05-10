"""TRIN (Arms Index) — single-symbol proxy.

The real Arms Index (Richard Arms, 1967) is exchange-wide:

    TRIN = (advancing issues / declining issues)
            / (advancing volume / declining volume)

Reading > 1 = bearish (more volume on declines than advances);
< 1 = bullish.

Single-symbol proxy substitutes "advancing issues" with bullish
bars (close >= open) and "advancing volume" with the volume on
those bars, computed over a trailing window:

    bull_count = number of bullish bars
    bear_count = number of bearish bars
    bull_vol   = volume on bullish bars
    bear_vol   = volume on bearish bars
    TRIN[i]    = (bull_count / bear_count) / (bull_vol / bear_vol)

Default ``period = 10``.

Output length equals input length. Indices ``0 .. period - 2``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Window with zero bear count or bear volume -> ``None``
      (degenerate ratio, caller branches).
"""

from __future__ import annotations

from collections.abc import Sequence


def trin_proxy(
    opens: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 10,
) -> list[float | None]:
    """Per-bar TRIN proxy over a trailing window."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(opens)
    if n != len(closes) or n != len(volumes):
        raise ValueError(
            f"opens, closes, volumes must have the same length; "
            f"got {n}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        bull_count = 0
        bear_count = 0
        bull_vol = 0.0
        bear_vol = 0.0
        for k in range(i - period + 1, i + 1):
            if closes[k] >= opens[k]:
                bull_count += 1
                bull_vol += volumes[k]
            else:
                bear_count += 1
                bear_vol += volumes[k]
        if bear_count == 0 or bear_vol == 0:
            # Degenerate window — leave None so caller branches.
            continue
        ratio_count = bull_count / bear_count
        ratio_vol = bull_vol / bear_vol
        if ratio_vol == 0:
            continue
        out[i] = ratio_count / ratio_vol
    return out


__all__ = ["trin_proxy"]
