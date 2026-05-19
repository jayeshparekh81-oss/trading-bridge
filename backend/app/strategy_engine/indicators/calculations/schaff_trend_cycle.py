"""Schaff Trend Cycle (STC) — Pine ``ta.stc`` parity.

Doug Schaff's cycle-aware MACD variant. Two stochastic + smoothing
passes over the MACD line produce a fast-moving 0..100 oscillator.

Definition (LOCKED per reference doc; Pine ``ta.stc(close, 10, 23, 50)``):
    macd = EMA(close, fast_length) - EMA(close, slow_length)

    # First stochastic + smoothing
    ll1[t] = lowest(macd[t - cycle_length + 1 .. t])
    hh1[t] = highest(macd[t - cycle_length + 1 .. t])
    if hh1 == ll1: stoch1[t] = stoch1[t-1] (carry-forward), else:
        stoch1[t] = 100 * (macd[t] - ll1[t]) / (hh1[t] - ll1[t])
    smooth1[t] = smooth1[t-1] + factor * (stoch1[t] - smooth1[t-1])

    # Second stochastic + smoothing
    ll2[t] = lowest(smooth1[t - cycle_length + 1 .. t])
    hh2[t] = highest(smooth1[t - cycle_length + 1 .. t])
    if hh2 == ll2: stoch2[t] = stoch2[t-1] (carry-forward), else:
        stoch2[t] = 100 * (smooth1[t] - ll2[t]) / (hh2[t] - ll2[t])
    stc[t] = stc[t-1] + factor * (stoch2[t] - stc[t-1])

    Defaults: fast_length=23, slow_length=50, cycle_length=10,
              factor=0.5.

    Initialize each smoothing state to the FIRST non-None stoch value
    seen (no SMA seed; the smoothing is its own seed).

    Output bounded roughly 0..100 (small overshoots possible from
    the smoothing).

Source: Doug Schaff original; Pine ``ta.stc`` reference implementation.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def schaff_trend_cycle(
    closes: Sequence[float],
    fast_length: int = 23,
    slow_length: int = 50,
    cycle_length: int = 10,
    factor: float = 0.5,
) -> list[float | None]:
    """Schaff Trend Cycle — Pine ``ta.stc`` parity."""
    _check_period(fast_length, "fast_length")
    _check_period(slow_length, "slow_length")
    _check_period(cycle_length, "cycle_length")
    if fast_length >= slow_length:
        raise ValueError(
            f"fast_length must be < slow_length; got fast={fast_length}, "
            f"slow={slow_length}."
        )
    if not isinstance(factor, (int, float)) or isinstance(factor, bool):
        raise ValueError(f"factor must be numeric; got {factor!r}.")
    if not (0.0 < factor <= 1.0):
        raise ValueError(f"factor must be in (0, 1]; got {factor}.")

    n = len(closes)
    if n == 0:
        return []

    # Step 1: MACD = EMA(fast) - EMA(slow). Both lists are length-n
    # with None for warm-up. MACD is None when either EMA is None.
    ema_fast = ema(list(closes), fast_length)
    ema_slow = ema(list(closes), slow_length)
    if not ema_fast or not ema_slow:
        return [None] * n

    macd: list[float | None] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd.append(None)
        else:
            macd.append(f - s)

    # Step 2: First stochastic + smoothing pass.
    stoch1 = _windowed_stoch(macd, cycle_length)
    smooth1 = _smoothing_pass(stoch1, factor)

    # Step 3: Second stochastic + smoothing pass.
    stoch2 = _windowed_stoch(smooth1, cycle_length)
    stc = _smoothing_pass(stoch2, factor)

    return stc


def _windowed_stoch(
    series: list[float | None], cycle: int
) -> list[float | None]:
    """Stochastic normalization with carry-forward on flat windows.

    For each t with t >= first_defined + cycle - 1:
        window = series[t - cycle + 1 .. t]  (all non-None values)
        ll = min(window); hh = max(window)
        if hh == ll: out[t] = out[t-1] (carry-forward, or None if first)
        else: out[t] = 100 * (series[t] - ll) / (hh - ll)
    """
    n = len(series)
    out: list[float | None] = [None] * n
    prev: float | None = None
    for t in range(n):
        if series[t] is None:
            continue
        # Build window: last `cycle` values ending at t, all non-None.
        start = t - cycle + 1
        if start < 0:
            continue
        window = series[start : t + 1]
        if any(v is None for v in window):
            continue
        ll = min(window)  # type: ignore[type-var]
        hh = max(window)  # type: ignore[type-var]
        if hh == ll:
            # Flat window — carry forward
            out[t] = prev
        else:
            out[t] = 100.0 * (series[t] - ll) / (hh - ll)  # type: ignore[operator]
            prev = out[t]
    return out


def _smoothing_pass(
    series: list[float | None], factor: float
) -> list[float | None]:
    """Apply EMA-style smoothing: out[t] = out[t-1] + factor * (in[t] - out[t-1]).

    Initialise to the first non-None value seen.
    """
    n = len(series)
    out: list[float | None] = [None] * n
    initialized = False
    state: float = 0.0
    for t in range(n):
        v = series[t]
        if v is None:
            continue
        if not initialized:
            state = v
            initialized = True
        else:
            state = state + factor * (v - state)
        out[t] = state
    return out


def _check_period(period: int, name: str) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"{name} must be a positive int; got {period!r}.")


__all__ = ["schaff_trend_cycle"]
