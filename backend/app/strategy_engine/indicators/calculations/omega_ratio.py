"""Omega Ratio — gains-to-losses ratio relative to a threshold.

Definition (Keating + Shadwick, 2002):

    For each return ``r`` in the window:
        gain = max(r - threshold, 0)
        loss = max(threshold - r, 0)

    Omega = sum(gains) / sum(losses)

Omega is bounded in ``[0, +inf)``. Values > 1 mean the strategy
generated more probability-weighted gain than loss above the
threshold over the window. Default threshold is ``0`` (any positive
return counts as gain).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(closes)`` -> ``[]``.
    * Window with no losses (all returns >= threshold) -> ``None``
      (Omega → +inf, undefined as a finite scalar).
"""

from __future__ import annotations

from collections.abc import Sequence


def omega_ratio(
    closes: Sequence[float],
    period: int = 252,
    threshold: float = 0.0,
) -> list[float | None]:
    """Omega Ratio over a trailing window."""
    _check_period(period)
    n = len(closes)
    if n == 0 or period >= n:
        return []

    returns: list[float | None] = [None] * n
    for i in range(1, n):
        prev = closes[i - 1]
        if prev == 0:
            continue
        returns[i] = closes[i] / prev - 1.0

    out: list[float | None] = [None] * n
    for i in range(period, n):
        window = returns[i - period + 1 : i + 1]
        if any(v is None for v in window):
            continue
        floats = [v for v in window if v is not None]
        gains = sum(max(r - threshold, 0.0) for r in floats)
        losses = sum(max(threshold - r, 0.0) for r in floats)
        if losses == 0.0:
            continue
        out[i] = gains / losses
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["omega_ratio"]
