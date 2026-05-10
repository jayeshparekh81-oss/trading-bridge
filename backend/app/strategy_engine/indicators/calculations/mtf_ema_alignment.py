"""Multi-timeframe EMA alignment score.

Computes N EMAs of close (default periods 20 / 50 / 200) and emits
a per-bar score in ``[-1.0, +1.0]`` based on how strongly they
agree on direction. With ``periods = (fast, ..., slow)`` (the
default 20 / 50 / 200 stack):

    +1.0  → fast EMA above each slower one (EMA20 > EMA50 > EMA200)
            → uptrend confirmation
    -1.0  → fast EMA below each slower one (EMA20 < EMA50 < EMA200)
            → downtrend confirmation
     0.0  → mixed / inconclusive

Despite the name "multi-timeframe" this implementation runs all
EMAs on the **same** candle series — Phase 9 doesn't fetch
higher-timeframe series in the calc layer. The "multi-timeframe"
intent (different EMAs approximate different timeframes' moving
averages) holds because EMA(N) on M-minute bars approximates
EMA(M_other) on a slower bar series under regular price
distributions. Document explicitly so a future reader doesn't
expect cross-timeframe fetches.

Output length equals input length. ``None`` for the warm-up of
the *slowest* EMA.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from app.strategy_engine.indicators.calculations.ema import ema


def mtf_ema_alignment(
    closes: Sequence[float],
    periods: tuple[int, ...] = (20, 50, 200),
) -> list[float | None]:
    """Per-bar alignment score over the supplied EMA periods.

    ``periods`` defaults to the conventional 20 / 50 / 200 stack.
    Pass any 2+ ascending periods; the function asserts the order
    so a typo in the config is caught up-front.
    """
    if len(periods) < 2:
        raise ValueError(
            f"periods must have at least 2 entries; got {periods!r}."
        )
    for prev, nxt in pairwise(periods):
        if nxt <= prev:
            raise ValueError(
                f"periods must be strictly ascending; got {periods!r}."
            )
    n = len(closes)
    if n == 0 or max(periods) > n:
        return []

    series = [ema(list(closes), p) for p in periods]
    if not all(series):
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        raw = [s[i] for s in series]
        if any(v is None for v in raw):
            continue
        # The ``is None`` guard above narrows for runtime but mypy
        # can't infer that across the list comprehension; rebuild
        # the list with explicit float typing so the comparisons
        # type-check cleanly.
        values: list[float] = [v for v in raw if v is not None]
        if len(values) != len(raw):
            continue  # safety belt — should be unreachable
        # In an uptrend the fast EMA is *higher* than the slow
        # EMA — so values[0] (fast) > values[k] (slower) for all k.
        # That's strictly DESCENDING in list order. Hence:
        #   uptrend   → values strictly descending in list order → +1
        #   downtrend → values strictly ascending  in list order → -1
        uptrend = all(a > b for a, b in pairwise(values))
        downtrend = all(a < b for a, b in pairwise(values))
        if uptrend:
            out[i] = 1.0
        elif downtrend:
            out[i] = -1.0
        else:
            out[i] = 0.0
    return out


__all__ = ["mtf_ema_alignment"]
