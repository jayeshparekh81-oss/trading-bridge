"""Volume Zone Oscillator (VZO) - Walid Khalil, 2009.

Definition::

    vp[i]  = volume[i] if close[i] > close[i - 1] else -volume[i]
    ema_vp = EMA(vp, period)
    ema_tv = EMA(volume, period)
    VZO[i] = (ema_vp[i] / ema_tv[i]) * 100

Output range typically ``[-60, +60]`` (clamped to ``[-100, +100]``
by construction). Khalil's interpretation:
    > 40   bullish zone
    -40..40 neutral
    < -40  bearish zone

Output length matches input. ``None`` for bars where ``ema_tv == 0``
(no volume context).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def volume_zone_oscillator(
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """VZO line."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be int >= 2; got {period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must match in length; got {n}, {len(volumes)}."
        )
    if n == 0:
        return []
    vp: list[float] = [0.0] * n
    for i in range(1, n):
        vp[i] = volumes[i] if closes[i] > closes[i - 1] else -volumes[i]
    ema_vp = ema(vp, period)
    ema_tv = ema(list(volumes), period)
    if not ema_vp or not ema_tv:
        return [None] * n
    out: list[float | None] = [None] * n
    for i in range(n):
        v = ema_vp[i]
        t = ema_tv[i]
        if v is None or t is None or t == 0:
            continue
        out[i] = (v / t) * 100.0
    return out


__all__ = ["volume_zone_oscillator"]
