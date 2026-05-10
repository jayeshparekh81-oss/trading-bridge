"""Round-number attraction - boolean flag for nearby strike-grid magnetism.

Markets often hesitate, consolidate, or reverse near round
numbers (psychological levels + options open-interest clusters
at strike grid points). This indicator flags bars whose close is
within ``threshold_pct`` of the nearest round-number strike.

Per-bar code:

    1.0 -> close is within ``threshold_pct`` of nearest strike
    0.0 -> not near a round number

Defaults ``strike_step = 100`` (NIFTY-style grid),
``threshold_pct = 0.5`` (within 0.5 %).

Output length equals input length. No warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``strike_step <= 0`` or ``threshold_pct <= 0`` -> ``ValueError``.
    * Nearest strike == 0 -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def round_number_attraction(
    closes: Sequence[float],
    strike_step: float = 100.0,
    threshold_pct: float = 0.5,
) -> list[float | None]:
    """1 / 0 per bar based on proximity to nearest round-number strike."""
    if not isinstance(strike_step, (int, float)) or isinstance(strike_step, bool):
        raise ValueError(f"strike_step must be a number; got {strike_step!r}.")
    if strike_step <= 0:
        raise ValueError(f"strike_step must be > 0; got {strike_step}.")
    if not isinstance(threshold_pct, (int, float)) or isinstance(threshold_pct, bool):
        raise ValueError(f"threshold_pct must be a number; got {threshold_pct!r}.")
    if threshold_pct <= 0:
        raise ValueError(f"threshold_pct must be > 0; got {threshold_pct}.")
    n = len(closes)
    if n == 0:
        return []
    out: list[float | None] = [None] * n
    for i in range(n):
        nearest = round(closes[i] / strike_step) * strike_step
        if nearest == 0:
            continue
        distance_pct = abs(closes[i] - nearest) / nearest * 100.0
        out[i] = 1.0 if distance_pct <= threshold_pct else 0.0
    return out


__all__ = ["round_number_attraction"]
