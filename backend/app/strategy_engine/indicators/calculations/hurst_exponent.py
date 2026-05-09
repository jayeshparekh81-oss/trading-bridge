"""Hurst Exponent — trend persistence vs mean-reversion.

Computed via the Rescaled-Range (R/S) method over a trailing
window. Output ``H`` is in roughly ``[0, 1]``:

    H < 0.5    -> mean-reverting (anti-persistent)
    H ≈ 0.5    -> random walk
    H > 0.5    -> trending (persistent)

Algorithm (per window of length ``period``):

    1. Build the log-return series of the window's closes.
    2. For each lag in ``lags = [4, 8, 16, 32, ...]`` up to
       ``period // 2``:
        chunks = split returns into non-overlapping chunks of
                 length ``lag``
        For each chunk:
            mean = mean(chunk)
            cum  = cumulative sum of (chunk - mean)
            R    = max(cum) - min(cum)
            S    = stdev(chunk)
            RS   = R / S    (skip if S == 0)
        avg_RS[lag] = mean of RS across chunks (skip if no chunks
                      had S > 0).
    3. Linear-regress log(avg_RS) on log(lag); H = slope.

Pure stdlib — slightly slower than a numpy implementation but
matches the leaf-module convention of the rest of the calculations
package.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(closes)`` -> ``[]``.
    * Window where every lag fails (e.g. perfectly flat closes)
      -> ``None`` for that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def hurst_exponent(
    closes: Sequence[float], period: int = 100
) -> list[float | None]:
    """Hurst exponent from rolling Rescaled-Range analysis."""
    if not isinstance(period, int) or period < 16:
        # R/S analysis needs at least a few lag scales to be
        # stable. 16 is the practical minimum.
        raise ValueError(f"period must be an int >= 16; got {period!r}.")
    n = len(closes)
    if n == 0 or period > n:
        return []

    # Lags as powers of two up to period // 2; cap at 4 lag scales
    # so the regression has enough but not too many points.
    lags: list[int] = []
    lag = 4
    while lag <= period // 2 and len(lags) < 6:
        lags.append(lag)
        lag *= 2
    if len(lags) < 2:
        return [None] * n  # not enough lag scales for a slope.

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window_closes = closes[i - period + 1 : i + 1]
        log_returns: list[float] = []
        ok = True
        for k in range(1, period):
            prev = window_closes[k - 1]
            curr = window_closes[k]
            if prev <= 0 or curr <= 0:
                ok = False
                break
            log_returns.append(math.log(curr / prev))
        if not ok or not log_returns:
            continue

        log_lags: list[float] = []
        log_rs: list[float] = []
        for lg in lags:
            if lg > len(log_returns):
                continue
            num_chunks = len(log_returns) // lg
            rs_values: list[float] = []
            for c in range(num_chunks):
                chunk = log_returns[c * lg : (c + 1) * lg]
                mean_c = sum(chunk) / lg
                deviations = [v - mean_c for v in chunk]
                cum = 0.0
                max_cum = -math.inf
                min_cum = math.inf
                for d in deviations:
                    cum += d
                    if cum > max_cum:
                        max_cum = cum
                    if cum < min_cum:
                        min_cum = cum
                r = max_cum - min_cum
                var = sum((v - mean_c) ** 2 for v in chunk) / lg
                s = math.sqrt(var)
                if s == 0.0:
                    continue
                rs_values.append(r / s)
            if not rs_values:
                continue
            avg_rs = sum(rs_values) / len(rs_values)
            if avg_rs <= 0:
                continue
            log_lags.append(math.log(lg))
            log_rs.append(math.log(avg_rs))

        if len(log_lags) < 2:
            continue
        # Slope via simple least-squares.
        m_lag = sum(log_lags) / len(log_lags)
        m_rs = sum(log_rs) / len(log_rs)
        sxx = sum((lv - m_lag) ** 2 for lv in log_lags)
        sxy = sum(
            (lv - m_lag) * (rv - m_rs)
            for lv, rv in zip(log_lags, log_rs, strict=True)
        )
        if sxx == 0.0:
            continue
        out[i] = sxy / sxx
    return out


__all__ = ["hurst_exponent"]
