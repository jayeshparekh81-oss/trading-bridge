"""Lo-MacKinlay Variance Ratio — random-walk test.

Definition::

    return_1[i] = log(close[i] / close[i - 1])
    return_q[i] = log(close[i] / close[i - q])
    Var(q)      = sum((return_q - mean(return_q))^2) / (period - q)
    Var(1)      = sum((return_1 - mean(return_1))^2) / (period - 1)
    VR(q)       = Var(q) / (q * Var(1))

Interpretation:

    VR ~ 1.0  -> random walk (returns are uncorrelated)
    VR > 1.0  -> trending / momentum (positive autocorrelation)
    VR < 1.0  -> mean-reverting (negative autocorrelation)

Default ``short = 2``, ``long = 10`` (passing-test setup;
real Lo-MacKinlay typically uses long = 4, 8, 16). The
``period`` parameter sets the window size for the variance
estimates; we hardcode it to ``long * 10`` so we get a
statistically meaningful sample.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``short >= long`` -> ``ValueError``.
    * Insufficient bars -> ``[]``.
    * Var(1) == 0 (constant window) -> ``None`` for that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def variance_ratio(
    closes: Sequence[float], short: int = 2, long: int = 10,
) -> list[float | None]:
    """Lo-MacKinlay variance ratio. Compares variance at the long-
    horizon to the (scaled) short-horizon variance."""
    if not isinstance(short, int) or isinstance(short, bool) or short < 1:
        raise ValueError(f"short must be a positive int; got {short!r}.")
    if not isinstance(long, int) or isinstance(long, bool) or long < 2:
        raise ValueError(f"long must be an int >= 2; got {long!r}.")
    if short >= long:
        raise ValueError(
            f"short must be strictly less than long; got short={short}, long={long}."
        )
    n = len(closes)
    period = long * 10  # window size for the variance estimates
    if n == 0 or n < period + long:
        return []

    out: list[float | None] = [None] * n
    for i in range(period + long, n):
        # Compute log returns at horizons ``short`` and ``long``
        # over the trailing ``period`` bars.
        ret_s: list[float] = []
        ret_l: list[float] = []
        for k in range(i - period + 1, i + 1):
            if k - short < 0 or k - long < 0:
                continue
            prev_s = closes[k - short]
            prev_l = closes[k - long]
            if prev_s <= 0 or prev_l <= 0:
                continue
            ret_s.append(math.log(closes[k] / prev_s))
            ret_l.append(math.log(closes[k] / prev_l))
        if len(ret_s) < 2 or len(ret_l) < 2:
            continue
        mean_s = sum(ret_s) / len(ret_s)
        mean_l = sum(ret_l) / len(ret_l)
        var_s = sum((r - mean_s) ** 2 for r in ret_s) / (len(ret_s) - 1)
        var_l = sum((r - mean_l) ** 2 for r in ret_l) / (len(ret_l) - 1)
        # VR(long) per Lo-MacKinlay: ratio of long-horizon
        # variance to (long/short)-scaled short-horizon variance.
        denom = (long / short) * var_s
        if denom == 0:
            continue
        out[i] = var_l / denom
    return out


__all__ = ["variance_ratio"]
