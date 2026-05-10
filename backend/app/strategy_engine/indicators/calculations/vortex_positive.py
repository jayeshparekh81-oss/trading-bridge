"""Vortex Indicator — VI+ line (Botes & Siepman, 2009).

Definition::

    VM+[i] = abs(high[i]   - low[i - 1])
    VM-[i] = abs(low[i]    - high[i - 1])
    TR[i]  = true_range[i]
    VI+    = sum(VM+ over period) / sum(TR over period)
    VI-    = sum(VM- over period) / sum(TR over period)

VI+ rising while VI- falls signals an emerging uptrend; the inverse
signals a downtrend. Crossings of VI+ and VI- are classic entry
triggers.

Default ``period = 14``.

Output length equals input length. Indices ``0 .. period - 1`` are
``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n`` -> ``[]``.
    * ``sum(TR) == 0`` over the window -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def vortex_positive(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Vortex VI+ line."""
    return _vortex(highs, lows, closes, period, plus=True)


def _vortex(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
    *,
    plus: bool,
) -> list[float | None]:
    """Shared computation — :mod:`vortex_negative` calls this with
    ``plus=False``."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period >= n:
        return []

    vm: list[float] = [0.0]
    tr: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        if plus:
            vm.append(abs(highs[i] - lows[i - 1]))
        else:
            vm.append(abs(lows[i] - highs[i - 1]))
        tr.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    out: list[float | None] = [None] * n
    for i in range(period, n):
        vm_sum = sum(vm[i - period + 1 : i + 1])
        tr_sum = sum(tr[i - period + 1 : i + 1])
        if tr_sum == 0:
            continue
        out[i] = vm_sum / tr_sum
    return out


__all__ = ["vortex_positive"]
