"""True Strength Index (TSI, William Blau, 1991).

Definition::

    pc[i]      = close[i] - close[i - 1]                  # price change
    pc_smooth1 = EMA(pc, long)
    pc_smooth2 = EMA(pc_smooth1, short)
    abs_smooth1 = EMA(abs(pc), long)
    abs_smooth2 = EMA(abs_smooth1, short)
    TSI[i]     = 100 * pc_smooth2[i] / abs_smooth2[i]

Output range is roughly ``[-100, +100]``. Pine equivalent
``ta.tsi(source, short, long)``.

Defaults ``long = 25``, ``short = 13``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * Insufficient bars for both EMAs -> ``[]``.
    * abs_smooth2[i] == 0 -> ``None`` for that bar (degenerate).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def true_strength_index(
    closes: Sequence[float],
    long: int = 25,
    short: int = 13,
) -> list[float | None]:
    """TSI over double-smoothed price changes."""
    if not isinstance(long, int) or isinstance(long, bool) or long <= 0:
        raise ValueError(f"long must be a positive int; got {long!r}.")
    if not isinstance(short, int) or isinstance(short, bool) or short <= 0:
        raise ValueError(f"short must be a positive int; got {short!r}.")
    n = len(closes)
    if n == 0 or n < long + short:
        return []

    pc = [0.0] * n
    abs_pc = [0.0] * n
    for i in range(1, n):
        delta = closes[i] - closes[i - 1]
        pc[i] = delta
        abs_pc[i] = abs(delta)

    pc_s1 = ema(pc, long)
    abs_s1 = ema(abs_pc, long)
    if not pc_s1 or not abs_s1:
        return [None] * n
    pc_s1_filled = [v if v is not None else 0.0 for v in pc_s1]
    abs_s1_filled = [v if v is not None else 0.0 for v in abs_s1]
    pc_s2 = ema(pc_s1_filled, short)
    abs_s2 = ema(abs_s1_filled, short)
    if not pc_s2 or not abs_s2:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        p = pc_s2[i]
        a = abs_s2[i]
        if p is None or a is None or a == 0:
            continue
        out[i] = 100.0 * p / a
    return out


__all__ = ["true_strength_index"]
