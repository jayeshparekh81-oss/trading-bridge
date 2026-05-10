"""Variable Index Dynamic Average (VIDYA, Tushar Chande, 1992).

Substitute for the spec's ``hull_ma`` (already an active
indicator in the registry). VIDYA uses the absolute value of
Chande Momentum (CMO) as a per-bar volatility-index multiplier
on an EMA-style smoothing — fast in trending markets, near-
constant in chop. Mechanism is distinct from ``kaufman_ama``'s
efficiency-ratio adaptation (so the registry now offers two
genuinely-different adaptive MA flavours).

Definition::

    cmo[i]    = CMO(close, period)[i]                # range -100..+100
    vi[i]     = abs(cmo[i]) / 100                     # range 0..1
    alpha     = 2 / (period + 1)                      # base EMA factor
    seed:     VIDYA[period - 1] = SMA(close, period)[period - 1]
    VIDYA[i]  = alpha * vi[i] * close[i] + (1 - alpha * vi[i]) * VIDYA[i - 1]

Default ``period = 9`` (Chande's recommendation).

Output length equals input length. ``None`` for the warm-up
(first ``period - 1`` indices because CMO + SMA both need that).

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` rejected — CMO needs at least 2 bars.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.chande_momentum import (
    chande_momentum,
)


def vidya(
    values: Sequence[float],
    period: int = 9,
) -> list[float | None]:
    """VIDYA — CMO-adapted EMA."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(values)
    if n == 0 or period > n:
        return []

    cmo = chande_momentum(list(values), period)
    if not cmo:
        return [None] * n

    alpha = 2.0 / (period + 1)
    out: list[float | None] = [None] * n

    # Seed at index ``period - 1`` with the SMA of the first window.
    seed_idx = period - 1
    out[seed_idx] = sum(values[: period]) / period
    for i in range(seed_idx + 1, n):
        prev = out[i - 1]
        c = cmo[i]
        if prev is None or c is None:
            out[i] = prev
            continue
        vi = abs(c) / 100.0
        adaptive = alpha * vi
        out[i] = adaptive * values[i] + (1.0 - adaptive) * prev
    return out


__all__ = ["vidya"]
