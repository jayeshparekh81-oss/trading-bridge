"""TTM Squeeze - John Carter's BB-inside-KC squeeze detector.

Promotes the Phase-9 ``ttm_squeeze`` coming-soon stub to ACTIVE
(same registry-splat pattern as Pack 4 std_dev / camarilla_pivots
promotions).

Definition (Carter, *Mastering the Trade*, 2005):

    squeeze ON  when bb_upper < kc_upper AND bb_lower > kc_lower
    squeeze OFF otherwise

This calc emits a single 0.0 / 1.0 line: ``1.0`` when the squeeze
is on, ``0.0`` when it has fired (or never been on). Operators
combine with a momentum confirmation (e.g. histogram flip) to
trigger entries.

Output length matches input. ``None`` until both BB and KC have
seeded (max of bb_period and kc_period).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Periods or multiplier non-positive -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.bollinger_bands import (
    bollinger_bands,
)
from app.strategy_engine.indicators.calculations.keltner_channel import (
    keltner_channel,
)


def ttm_squeeze(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    bb_period: int = 20,
    kc_period: int = 20,
    bb_std: float = 2.0,
    kc_mult: float = 1.5,
) -> list[float | None]:
    """0/1 squeeze-state line over input bars."""
    if not isinstance(bb_period, int) or isinstance(bb_period, bool) or bb_period < 2:
        raise ValueError(f"bb_period must be int >= 2; got {bb_period!r}.")
    if not isinstance(kc_period, int) or isinstance(kc_period, bool) or kc_period < 2:
        raise ValueError(f"kc_period must be int >= 2; got {kc_period!r}.")
    if bb_std <= 0:
        raise ValueError(f"bb_std must be > 0; got {bb_std!r}.")
    if kc_mult <= 0:
        raise ValueError(f"kc_mult must be > 0; got {kc_mult!r}.")
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs/lows/closes must match in length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0:
        return []

    bb_u, _bb_m, bb_l = bollinger_bands(closes, bb_period, bb_std)
    kc_u, _kc_m, kc_l = keltner_channel(highs, lows, closes, kc_period, kc_mult)
    if not bb_u or not kc_u:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        bu = bb_u[i]
        bl = bb_l[i]
        ku = kc_u[i]
        kl = kc_l[i]
        if bu is None or bl is None or ku is None or kl is None:
            continue
        out[i] = 1.0 if (bu < ku and bl > kl) else 0.0
    return out


__all__ = ["ttm_squeeze"]
