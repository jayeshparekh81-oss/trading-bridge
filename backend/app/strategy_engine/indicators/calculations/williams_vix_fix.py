"""Williams VIX Fix (WVF) — synthetic VIX-like volatility from OHLC only.

Larry Williams' "VIX Fix" (2007) approximates VIX behaviour for any
instrument using only its own price data. Spikes flag capitulation
moments; the indicator is commonly used for long-side mean-reversion
entries near market lows.

Definition:
    WVF[i] = ((max(high[i - period + 1 .. i]) - low[i])
              / max(high[i - period + 1 .. i])) * 100

    For each bar ``i >= period - 1``:
        1. Compute the rolling ``period``-bar maximum of ``high``.
        2. Subtract today's ``low`` from that rolling maximum.
        3. Divide by the rolling maximum.
        4. Scale to percent.

    Default ``period = 22`` (Williams' original recommendation).
    Positions ``0 .. period - 2`` are ``None``.

Output is always non-negative because the rolling-high is, by
construction, >= low[i].

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``
    * Length mismatch between highs and lows -> ``ValueError``
    * ``period > n`` -> ``[]``
    * ``period == 1`` -> WVF[i] = (high[i] - low[i]) / high[i] * 100
      (single-bar window — degenerates to bar's range / high)
    * ``highest_high == 0`` -> ``None`` for that bar (division guard;
      unlikely on real price series but possible on test inputs)

Source: Larry Williams, "VIX Fix" — TradingView publication; standard
formula across Pine community.
"""

from __future__ import annotations

from collections.abc import Sequence


def williams_vix_fix(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 22,
) -> list[float | None]:
    """Larry Williams' VIX Fix — synthetic VIX for any OHLC stream."""
    _check_period(period)
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must be same length; got {n} vs {len(lows)}."
        )
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * (period - 1)

    # Use a simple "scan window for max" approach. Even for period=22 on
    # daily charts that's only ~22 comparisons per bar; the deque-based
    # O(1) max algorithm is overkill for this use case.
    for i in range(period - 1, n):
        window_high = max(highs[i - period + 1 : i + 1])
        if window_high == 0.0:
            out.append(None)
            continue
        wvf = (window_high - lows[i]) / window_high * 100.0
        out.append(wvf)

    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["williams_vix_fix"]
