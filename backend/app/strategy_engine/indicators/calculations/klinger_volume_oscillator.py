"""Klinger Volume Oscillator (KVO, Stephen Klinger 1997).

Substitute for the requested ``trix`` (already an active indicator
in the registry — Pack 2 / Phase 9). KVO is a heavily-requested
volume-weighted momentum oscillator; rare in the existing pack
mix, so it adds genuine new signal.

Definition::

    HLC[i] = (high + low + close) / 3
    trend[i] = +1 if HLC[i] > HLC[i - 1] else -1   (0 if equal)
    dm[i]    = high - low
    cm[i]    = cm[i - 1] + dm[i] if trend[i] == trend[i - 1] else dm[i - 1] + dm[i]
    vf[i]    = volume[i] * abs(2 * (dm[i] / cm[i]) - 1) * trend[i] * 100
                                                   (0 when cm[i] == 0)
    KVO      = EMA(vf, fast) - EMA(vf, slow)

Default fast/slow = 34/55 (Klinger's original recommendations).

Output length equals input length. ``None`` for the warm-up
(slow-EMA seed lands at index ``slow - 1``).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``slow >= n`` -> ``[]``.
    * ``fast >= slow`` -> ``ValueError``.
    * Flat trend (HLC unchanged) -> ``trend = 0`` for that bar; vf
      contribution is ``0`` regardless of cm/dm.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def klinger_volume_oscillator(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    fast: int = 34,
    slow: int = 55,
) -> list[float | None]:
    """Klinger Volume Oscillator over EMAs of the volume-force series."""
    _check_period(fast, "fast")
    _check_period(slow, "slow")
    if fast >= slow:
        raise ValueError(
            f"fast must be strictly less than slow; got fast={fast}, slow={slow}."
        )
    n = len(highs)
    if n != len(lows) or n != len(closes) or n != len(volumes):
        raise ValueError(
            "highs, lows, closes, volumes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}, {len(volumes)}."
        )
    if n == 0 or slow >= n:
        return []

    hlc = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]
    trend = [0] * n
    dm = [highs[i] - lows[i] for i in range(n)]
    cm = [0.0] * n
    vf = [0.0] * n

    for i in range(1, n):
        if hlc[i] > hlc[i - 1]:
            trend[i] = 1
        elif hlc[i] < hlc[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]
        if trend[i] == trend[i - 1]:
            cm[i] = cm[i - 1] + dm[i]
        else:
            cm[i] = dm[i - 1] + dm[i]
        if cm[i] == 0:
            vf[i] = 0.0
        else:
            vf[i] = volumes[i] * abs(2.0 * (dm[i] / cm[i]) - 1.0) * trend[i] * 100.0

    fast_ema = ema(vf, fast)
    slow_ema = ema(vf, slow)
    if not fast_ema or not slow_ema:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        f = fast_ema[i]
        s = slow_ema[i]
        if f is None or s is None:
            continue
        out[i] = f - s
    return out


def _check_period(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive int; got {value!r}.")


__all__ = ["klinger_volume_oscillator"]
