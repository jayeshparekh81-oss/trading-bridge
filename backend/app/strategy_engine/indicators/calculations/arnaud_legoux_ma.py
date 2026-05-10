"""Arnaud Legoux Moving Average (ALMA, Arnaud Legoux & Dimitrios Kouzis-Loukas, 2009).

Substitute for the spec's ``tema`` (already an active indicator
in the registry — Phase 9 / Pack 2 era). ALMA applies a Gaussian-
weighted kernel to the trailing window and is markedly faster +
smoother than EMA on responsive price action.

Definition::

    m = floor(offset * (period - 1))                  # peak position
    s = period / sigma                                # kernel width
    w[k] = exp(-(k - m)^2 / (2 * s^2))                # Gaussian weights
    ALMA = sum(w[k] * value[i - period + 1 + k]) / sum(w)

Defaults ``period = 9``, ``sigma = 6``, ``offset = 0.85``
(Legoux's original recommendations).

Output length equals input length. ``None`` for the warm-up
(first ``period - 1`` indices).

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` rejected.
    * ``sigma <= 0`` rejected (would div-by-zero).
    * ``offset`` clipped to ``[0, 1]``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def arnaud_legoux_ma(
    values: Sequence[float],
    period: int = 9,
    sigma: float = 6.0,
    offset: float = 0.85,
) -> list[float | None]:
    """ALMA over a Gaussian-weighted ``period``-bar kernel."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    if not isinstance(sigma, (int, float)) or isinstance(sigma, bool):
        raise ValueError(f"sigma must be a number; got {sigma!r}.")
    if sigma <= 0:
        raise ValueError(f"sigma must be > 0; got {sigma}.")
    if not isinstance(offset, (int, float)) or isinstance(offset, bool):
        raise ValueError(f"offset must be a number; got {offset!r}.")
    if offset < 0 or offset > 1:
        raise ValueError(f"offset must be in [0, 1]; got {offset}.")
    n = len(values)
    if n == 0 or period > n:
        return []

    m = math.floor(offset * (period - 1))
    s = period / sigma
    weights = [math.exp(-((k - m) ** 2) / (2.0 * s * s)) for k in range(period)]
    weight_sum = sum(weights)
    if weight_sum == 0:
        return [None] * n  # defensive — sigma extreme would zero this out

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        weighted = sum(w * x for w, x in zip(weights, window, strict=True))
        out[i] = weighted / weight_sum
    return out


__all__ = ["arnaud_legoux_ma"]
