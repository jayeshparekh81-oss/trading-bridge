"""Martin Ratio — return / Ulcer Index (Peter Martin, 1987).

Risk-adjusted return measure using the Ulcer Index as the
denominator (rather than Sharpe's stddev or Sortino's downside
stddev). Penalises drawdowns by depth + duration — closer to
how a real trader experiences pain than stddev-based metrics.

Definition::

    period_return[i] = (close[i] - close[i - period]) / close[i - period] * 100
    UI[i]            = ulcer_index(close, period)[i]
    Martin[i]        = period_return[i] / UI[i]

Default ``period = 14``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
    * UI == 0 (no drawdowns in the window) -> ``+inf`` if return
      is positive, ``0`` if return is zero, ``-inf`` if return is
      negative. Caller branches on these sentinels.
    * ``close[i - period] == 0`` -> ``None`` for that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ulcer_index import ulcer_index


def martin_ratio(
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Martin Ratio (period return / Ulcer Index)."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []

    ui = ulcer_index(list(closes), period)
    if not ui:
        return [None] * n
    out: list[float | None] = [None] * n
    for i in range(period, n):
        prev = closes[i - period]
        if prev == 0:
            continue
        ret = (closes[i] - prev) / prev * 100.0
        denom = ui[i]
        if denom is None:
            continue
        if denom == 0:
            if ret > 0:
                out[i] = math.inf
            elif ret < 0:
                out[i] = -math.inf
            else:
                out[i] = 0.0
        else:
            out[i] = ret / denom
    return out


__all__ = ["martin_ratio"]
