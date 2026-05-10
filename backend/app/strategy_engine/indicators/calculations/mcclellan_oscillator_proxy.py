"""McClellan Oscillator — single-symbol proxy.

The real McClellan Oscillator (Sherman & Marian McClellan, 1969)
takes an exchange-wide net advances-declines stream and emits:

    EMA(net_AD, fast) - EMA(net_AD, slow)

Defaults are 19 / 39 — exponential smoothing factors of
0.10 and 0.05 respectively in McClellan's original.

Single-symbol proxy uses bar direction (close >= open ? +1 :
-1) as the net-AD stream. Output is centred near zero; positive
= net buying momentum across the recent window, negative = net
selling.

Defaults ``fast = 19``, ``slow = 39``.

Output length equals input length. ``None`` for the slow-EMA
warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``slow >= n`` -> ``[]``.
    * ``fast >= slow`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def mcclellan_oscillator_proxy(
    opens: Sequence[float],
    closes: Sequence[float],
    fast: int = 19,
    slow: int = 39,
) -> list[float | None]:
    """Single-symbol McClellan Oscillator proxy."""
    if not isinstance(fast, int) or isinstance(fast, bool) or fast <= 0:
        raise ValueError(f"fast must be a positive int; got {fast!r}.")
    if not isinstance(slow, int) or isinstance(slow, bool) or slow <= 0:
        raise ValueError(f"slow must be a positive int; got {slow!r}.")
    if fast >= slow:
        raise ValueError(
            f"fast must be strictly less than slow; got fast={fast}, slow={slow}."
        )
    n = len(opens)
    if n != len(closes):
        raise ValueError(
            f"opens and closes must have the same length; got {n}, {len(closes)}."
        )
    if n == 0 or slow >= n:
        return []

    bar_sign: list[float] = [
        1.0 if closes[i] >= opens[i] else -1.0 for i in range(n)
    ]
    fast_ema = ema(bar_sign, fast)
    slow_ema = ema(bar_sign, slow)
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


__all__ = ["mcclellan_oscillator_proxy"]
