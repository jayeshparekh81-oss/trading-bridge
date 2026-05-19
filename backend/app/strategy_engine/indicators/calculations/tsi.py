"""True Strength Index (TSI) — Pine ``ta.tsi`` parity.

William Blau's True Strength Index — double-smoothed momentum ratio.

Definition (matches Pine ``ta.tsi(close, long, short)``):
    PC[i]   = close[i] - close[i - 1]                       (PC[0] = None)
    APC[i]  = |PC[i]|

    EMA1_pc      = EMA(PC,   long)                          (SMA-seeded EMA)
    EMA2_pc      = EMA(EMA1_pc, short)
    EMA1_abspc   = EMA(APC,  long)
    EMA2_abspc   = EMA(EMA1_abspc, short)

    TSI[i] = 100 * EMA2_pc[i] / EMA2_abspc[i]

    Default ``long = 25``, ``short = 13``.

The PC series effectively starts at index 1 (no diff for the very first
bar). The first defined TSI output is at index ``1 + (long - 1) +
(short - 1) = long + short - 1`` (sums of the warm-ups of the diff +
both nested EMAs).

Source: Pine v5 ``ta.tsi`` reference; William Blau, "Momentum, Direction
and Divergence" (1996).

Edge cases:
    * Empty input -> ``[]``
    * Total warm-up exceeds n -> ``[]``
    * EMA2_abspc[i] == 0 (zero-momentum series) -> ``None`` for that bar
    * Invalid period -> ``ValueError``
"""

from __future__ import annotations

from collections.abc import Sequence


def tsi(
    values: Sequence[float],
    long_period: int = 25,
    short_period: int = 13,
) -> list[float | None]:
    """True Strength Index — Pine ``ta.tsi`` parity."""
    _check_period(long_period, "long_period")
    _check_period(short_period, "short_period")
    n = len(values)
    if n == 0:
        return []

    # PC at index 0 is None; otherwise close[i] - close[i-1].
    # Treat the series from index 1 onward as the EMA input.
    pc_values: list[float] = []
    abs_pc_values: list[float] = []
    for i in range(1, n):
        diff = float(values[i]) - float(values[i - 1])
        pc_values.append(diff)
        abs_pc_values.append(abs(diff))

    # EMA1 — period == long_period — over pc and abs_pc.
    # SMA-seeded EMA: first defined index = long_period - 1.
    ema1_pc = _sma_seeded_ema(pc_values, long_period)
    ema1_abspc = _sma_seeded_ema(abs_pc_values, long_period)
    if not ema1_pc:
        return [None] * n  # too short for EMA1

    # EMA2 — period == short_period — over EMA1 sequences.
    # Need to extract the contiguous defined tail of EMA1 for EMA2 input.
    ema2_pc = _double_ema(ema1_pc, short_period)
    ema2_abspc = _double_ema(ema1_abspc, short_period)

    # Re-align: ema1_pc / ema2_pc are aligned to the pc_values index
    # space (which starts at original index 1). Re-index into original
    # `values` space.
    out: list[float | None] = [None] * n
    for idx_in_pc in range(len(ema2_pc)):
        pc_val = ema2_pc[idx_in_pc]
        abs_val = ema2_abspc[idx_in_pc]
        if pc_val is None or abs_val is None:
            continue
        if abs_val == 0.0:
            # Series with zero momentum throughout the smoothing window.
            continue
        original_idx = idx_in_pc + 1  # pc_values[k] corresponds to original index k+1
        out[original_idx] = 100.0 * pc_val / abs_val

    return out


def _sma_seeded_ema(values: list[float], period: int) -> list[float | None]:
    """Pine ``ta.ema`` parity — SMA seed at index ``period - 1``."""
    n = len(values)
    if n == 0 or period > n:
        return []
    out: list[float | None] = [None] * (period - 1)
    alpha = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    prev = seed
    for i in range(period, n):
        cur = alpha * values[i] + (1 - alpha) * prev
        out.append(cur)
        prev = cur
    return out


def _double_ema(
    ema1: list[float | None], short_period: int
) -> list[float | None]:
    """Apply EMA over an already-EMA-smoothed series.

    Treats the first `short_period` contiguous non-None values as the
    SMA seed for the second EMA. Returns a list aligned to ``ema1``'s
    index space (None where the second EMA isn't yet defined).
    """
    n = len(ema1)
    out: list[float | None] = [None] * n

    # Find first contiguous non-None block.
    first_defined: int | None = None
    for i, v in enumerate(ema1):
        if v is not None:
            first_defined = i
            break
    if first_defined is None:
        return out

    seed_end = first_defined + short_period
    if seed_end > n:
        return out  # not enough EMA1 values to seed EMA2

    seed_window = ema1[first_defined:seed_end]
    if any(v is None for v in seed_window):
        return out
    seed = sum(seed_window) / short_period  # type: ignore[arg-type]
    out[seed_end - 1] = seed
    prev = seed
    alpha = 2.0 / (short_period + 1)
    for i in range(seed_end, n):
        v = ema1[i]
        if v is None:
            out[i] = None
            prev = prev  # keep prev — should not happen in practice
            continue
        cur = alpha * v + (1 - alpha) * prev
        out[i] = cur
        prev = cur
    return out


def _check_period(period: int, name: str) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"{name} must be a positive int; got {period!r}.")


__all__ = ["tsi"]
