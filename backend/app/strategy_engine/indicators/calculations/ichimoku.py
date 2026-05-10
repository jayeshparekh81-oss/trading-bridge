"""Ichimoku basic — Tenkan-sen + Kijun-sen.

Phase 9 ships only the two median-of-extremes lines:

    Tenkan-sen (Conversion) = (highest_high(N) + lowest_low(N)) / 2,
                              N = ``tenkan_period`` (default 9).
    Kijun-sen  (Base)       = (highest_high(M) + lowest_low(M)) / 2,
                              M = ``kijun_period`` (default 26).

The full Ichimoku cloud (Senkou A/B, Chikou) requires a forward shift
that the Phase 1 fixed-length contract does not currently express; the
cloud lands in Phase 11 alongside the simulator's session awareness.

Output length equals input length. Tenkan / Kijun are defined from
index ``tenkan_period - 1`` / ``kijun_period - 1`` respectively; earlier
indices are ``None``.

Edge cases per Phase 1 contract:
    * Empty input or mismatched lengths -> ``[]`` / ``ValueError``.
    * ``kijun_period > len(highs)`` -> Kijun is all ``None``; Tenkan
      may still seed if ``tenkan_period <= len(highs)``.
"""

from __future__ import annotations

from collections.abc import Sequence


def ichimoku(
    highs: Sequence[float],
    lows: Sequence[float],
    tenkan_period: int = 9,
    kijun_period: int = 26,
) -> tuple[list[float | None], list[float | None]]:
    """Return ``(tenkan, kijun)``."""
    _check_period(tenkan_period, "tenkan_period")
    _check_period(kijun_period, "kijun_period")
    if tenkan_period >= kijun_period:
        raise ValueError(
            f"tenkan_period ({tenkan_period}) must be < kijun_period ({kijun_period})."
        )

    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0:
        return [], []

    tenkan = _midline(highs, lows, tenkan_period, n)
    kijun = _midline(highs, lows, kijun_period, n)
    return tenkan, kijun


def _midline(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int,
    n: int,
) -> list[float | None]:
    out: list[float | None] = [None] * n
    if period > n:
        return out
    for i in range(period - 1, n):
        window_high = max(highs[i - period + 1 : i + 1])
        window_low = min(lows[i - period + 1 : i + 1])
        out[i] = (window_high + window_low) / 2.0
    return out


def _check_period(period: int, name: str) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"{name} must be a positive int; got {period!r}.")


__all__ = ["ichimoku"]
