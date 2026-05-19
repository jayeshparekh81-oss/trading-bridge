"""Accumulative Swing Index (ASI) — Wilder, 1978.

Cumulative running sum of the Swing Index (see swing_index.py).

Definition (LOCKED per reference doc):
    ASI[0] = SI[0]                  # which is 0 by convention
    ASI[t] = ASI[t-1] + SI[t]

Composes the existing ``swing_index()`` calc — no duplication of math.

Output length equals input length. Same parameters as Swing Index.

Source: J. Welles Wilder, "New Concepts in Technical Trading Systems"
(1978).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.swing_index import swing_index


def accumulative_swing_index(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    limit_move: float = 1.0,
) -> list[float]:
    """Accumulative Swing Index — running cumulative sum of SI."""
    si = swing_index(opens, highs, lows, closes, limit_move=limit_move)
    if not si:
        return []
    out: list[float] = [si[0]]
    for i in range(1, len(si)):
        out.append(out[-1] + si[i])
    return out


__all__ = ["accumulative_swing_index"]
