"""Accelerator Oscillator (AC) — Bill Williams.

Second-derivative-flavoured momentum indicator. Where the Awesome
Oscillator (AO) reads price-momentum velocity, AC reads momentum
acceleration: AC = AO - SMA(AO, period).

Definition::

    median[i] = (high[i] + low[i]) / 2
    AO[i]     = SMA(median, fast) - SMA(median, slow)         (ao_fast/ao_slow)
    AC[i]     = AO[i] - SMA(AO, period)                       (ac_smoothing)

    Default ``ao_fast = 5``, ``ao_slow = 34``, ``ac_smoothing = 5`` —
    Bill Williams' original parameters from "New Trading Dimensions".

    The first defined position is at index ``ao_slow + ac_smoothing - 2``
    (AO needs ``ao_slow - 1`` warm-up bars; then SMA(AO) needs another
    ``ac_smoothing - 1``).

Edge cases per Phase 1 contract:
    * Empty / length-mismatch -> ``[]`` / ``ValueError``
    * ``ao_fast >= ao_slow`` -> ``ValueError``
    * Any period <= 0 or non-int -> ``ValueError``
    * Series too short for the combined warm-up -> ``[]``

Source: Bill Williams, "New Trading Dimensions" (1998). Standard
Pine community implementation.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.awesome_oscillator import (
    awesome_oscillator,
)


def accelerator_oscillator(
    highs: Sequence[float],
    lows: Sequence[float],
    ao_fast: int = 5,
    ao_slow: int = 34,
    ac_smoothing: int = 5,
) -> list[float | None]:
    """Bill Williams' Accelerator Oscillator."""
    _check_period(ao_fast, "ao_fast")
    _check_period(ao_slow, "ao_slow")
    _check_period(ac_smoothing, "ac_smoothing")
    if ao_fast >= ao_slow:
        raise ValueError(
            f"ao_fast must be strictly less than ao_slow; "
            f"got ao_fast={ao_fast}, ao_slow={ao_slow}."
        )
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0:
        return []

    # AO returns a list of length n with None for the first ao_slow - 1 bars.
    ao = awesome_oscillator(highs, lows, fast=ao_fast, slow=ao_slow)
    if not ao:
        return []

    # AC = AO - SMA(AO, ac_smoothing). The SMA of AO can only be
    # computed when the window has ac_smoothing non-None AO values —
    # i.e., starting at index (ao_slow - 1) + (ac_smoothing - 1).
    out: list[float | None] = [None] * n
    first_defined = ao_slow - 1 + ac_smoothing - 1
    if first_defined >= n:
        return out  # all-None — not enough bars

    for i in range(first_defined, n):
        window = ao[i - ac_smoothing + 1 : i + 1]
        # All values in this window should be non-None by construction;
        # guard defensively for downstream safety.
        if any(v is None for v in window):
            out[i] = None
            continue
        sma_ao = sum(window) / ac_smoothing  # type: ignore[arg-type]
        out[i] = ao[i] - sma_ao  # type: ignore[operator]
    return out


def _check_period(period: int, name: str) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"{name} must be a positive int; got {period!r}.")


__all__ = ["accelerator_oscillator"]
