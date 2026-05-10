"""ATM strike distance - % distance from the nearest at-the-money strike.

For each bar, identifies the nearest options-strike grid level
(integer multiple of ``strike_step``) and emits the % distance
from it. Useful for options strategies that want to position
relative to ATM (e.g. "wait for price to be < 0.3 % from ATM
before selling straddles").

Definition::

    nearest_strike = round(close / strike_step) * strike_step
    distance_pct   = (close - nearest_strike) / nearest_strike * 100

Output range is roughly ``[-strike_step/2, +strike_step/2]`` as
a percentage.

Default ``strike_step = 100`` (matches NIFTY's typical strike
gap; use 50 for BANKNIFTY index, 5/10/25 for individual stocks).

Output length equals input length. No warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``strike_step <= 0`` -> ``ValueError``.
    * Nearest strike == 0 (e.g. close near zero) -> ``None`` for
      that bar (degenerate).
"""

from __future__ import annotations

from collections.abc import Sequence


def atm_strike_distance(
    closes: Sequence[float],
    strike_step: float = 100.0,
) -> list[float | None]:
    """Per-bar % distance from the nearest options strike."""
    if not isinstance(strike_step, (int, float)) or isinstance(strike_step, bool):
        raise ValueError(f"strike_step must be a number; got {strike_step!r}.")
    if strike_step <= 0:
        raise ValueError(f"strike_step must be > 0; got {strike_step}.")
    n = len(closes)
    if n == 0:
        return []
    out: list[float | None] = [None] * n
    for i in range(n):
        nearest = round(closes[i] / strike_step) * strike_step
        if nearest == 0:
            continue
        out[i] = (closes[i] - nearest) / nearest * 100.0
    return out


__all__ = ["atm_strike_distance"]
