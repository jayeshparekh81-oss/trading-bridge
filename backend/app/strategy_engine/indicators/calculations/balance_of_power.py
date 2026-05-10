"""Balance of Power (Igor Livshin).

Per-bar measure of who controlled the session — buyers (positive)
or sellers (negative).

Definition::

    BoP[i] = (close[i] - open[i]) / (high[i] - low[i])     (0 if H == L)

Output range is ``[-1, +1]``. Index 0 is defined (no warm-up).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Flat bar (high == low) -> 0 that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def balance_of_power(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """Per-bar Balance of Power."""
    n = len(opens)
    if n != len(highs) or n != len(lows) or n != len(closes):
        raise ValueError(
            f"opens, highs, lows, closes must have the same length; "
            f"got {n}, {len(highs)}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return []
    out: list[float | None] = [0.0] * n
    for i in range(n):
        rng = highs[i] - lows[i]
        out[i] = 0.0 if rng == 0 else (closes[i] - opens[i]) / rng
    return out


__all__ = ["balance_of_power"]
