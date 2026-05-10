"""Mass Index (Donald Dorsey, 1992).

Definition::

    HL          = high - low                                       # bar range
    EMA_HL      = EMA(HL, ema_period)                              # default 9
    EMA_EMA_HL  = EMA(EMA_HL, ema_period)                          # default 9
    ratio       = EMA_HL / EMA_EMA_HL
    MI          = sum(ratio over sum_period bars)                  # default 25

Originally meant to detect *trend reversals* by spotting bulges
in the bar-range envelope. Dorsey's "reversal bulge" rule:
``MI > 27 then dips below 26.5`` ⇒ likely reversal.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Flat bar (high == low) contributes 0 — the EMA absorbs it.
    * ``EMA_EMA_HL[i] == 0`` -> ratio is 0 (avoids div-by-zero).
    * Insufficient bars (``ema_period * 2 + sum_period > n``) -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def mass_index(
    highs: Sequence[float],
    lows: Sequence[float],
    ema_period: int = 9,
    sum_period: int = 25,
) -> list[float | None]:
    """Dorsey's Mass Index."""
    _check_period(ema_period, "ema_period")
    _check_period(sum_period, "sum_period")
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0:
        return []
    # Rough warm-up: two EMA stages need ~2 * ema_period bars
    # before the ratio stabilises, then sum_period bars on top.
    minimum = ema_period * 2 + sum_period
    if n < minimum:
        return []

    hl = [highs[i] - lows[i] for i in range(n)]
    ema_hl = ema(hl, ema_period)
    if not ema_hl:
        return [None] * n
    # Feed the first EMA into the second. Replace warm-up Nones
    # with 0 so the second-stage EMA can seed; the resulting
    # warm-up region is filtered out by the ``sum_period`` window.
    ema_hl_filled = [v if v is not None else 0.0 for v in ema_hl]
    ema_ema_hl = ema(ema_hl_filled, ema_period)
    if not ema_ema_hl:
        return [None] * n

    ratio = [0.0] * n
    for i in range(n):
        a = ema_hl[i]
        b = ema_ema_hl[i]
        if a is None or b is None or b == 0:
            ratio[i] = 0.0
        else:
            ratio[i] = a / b

    out: list[float | None] = [None] * n
    for i in range(sum_period - 1, n):
        out[i] = sum(ratio[i - sum_period + 1 : i + 1])
    return out


def _check_period(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive int; got {value!r}.")


__all__ = ["mass_index"]
