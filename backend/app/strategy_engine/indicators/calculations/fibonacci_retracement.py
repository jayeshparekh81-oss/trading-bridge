"""Fibonacci retracement levels from a trailing swing high/low window.

Computes the 23.6%, 38.2%, 50%, 61.8%, 78.6% retracement levels
between the highest high and the lowest low in a trailing
``lookback``-bar window.

Two output orientations:
    * **Bullish** (default; ``direction='bull'``) — retracement of a
      DOWNswing from ``swing_high`` to ``swing_low``. Higher % =
      stronger retracement toward the original high. Standard "buy
      the dip" zone is 38.2% – 61.8%.

        level_pct = swing_low + (swing_high - swing_low) * pct

    * **Bearish** (``direction='bear'``) — retracement of an UPswing
      from ``swing_low`` to ``swing_high``. Same numbers; the
      strategy use case flips ("sell the bounce").

        level_pct = swing_high - (swing_high - swing_low) * pct

Returns a list of dicts (one per input bar) with keys
``{"swing_high", "swing_low", "23.6", "38.2", "50.0", "61.8", "78.6"}``
or ``None`` for warm-up bars (first ``lookback - 1`` indices).

Edge cases:
    * Empty input -> ``[]``
    * ``lookback < 2`` rejected
    * ``direction not in ('bull', 'bear')`` rejected
    * Length mismatch between highs and lows -> ``ValueError``
    * Flat window (high == low) -> all 5 levels equal to swing_high
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal


_FIB_PCTS: tuple[float, ...] = (0.236, 0.382, 0.500, 0.618, 0.786)
_FIB_KEYS: tuple[str, ...] = ("23.6", "38.2", "50.0", "61.8", "78.6")


def fibonacci_retracement(
    highs: Sequence[float],
    lows: Sequence[float],
    lookback: int = 50,
    direction: Literal["bull", "bear"] = "bull",
) -> list[dict[str, float] | None]:
    """Fibonacci retracement levels per bar."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 2:
        raise ValueError(f"lookback must be int >= 2; got {lookback!r}.")
    if direction not in ("bull", "bear"):
        raise ValueError(
            f"direction must be 'bull' or 'bear'; got {direction!r}."
        )
    n = len(highs)
    if len(lows) != n:
        raise ValueError(
            f"highs/lows length mismatch: highs={n}, lows={len(lows)}."
        )
    if n == 0:
        return []

    out: list[dict[str, float] | None] = [None] * n
    for i in range(lookback - 1, n):
        window_highs = highs[i - lookback + 1 : i + 1]
        window_lows = lows[i - lookback + 1 : i + 1]
        swing_h = max(window_highs)
        swing_l = min(window_lows)
        rng = swing_h - swing_l
        levels: dict[str, float] = {
            "swing_high": float(swing_h),
            "swing_low": float(swing_l),
        }
        for pct, key in zip(_FIB_PCTS, _FIB_KEYS, strict=True):
            if direction == "bull":
                levels[key] = float(swing_l + rng * pct)
            else:
                levels[key] = float(swing_h - rng * pct)
        out[i] = levels
    return out


__all__ = ["fibonacci_retracement"]
