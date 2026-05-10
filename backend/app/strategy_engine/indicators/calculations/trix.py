"""TRIX — triple-smoothed EMA momentum.

Definition (Hutson, 1983; Pine ``ta.trix``):

    EMA1 = EMA(values, period)
    EMA2 = EMA(EMA1, period)
    EMA3 = EMA(EMA2, period)
    TRIX = 100 * (EMA3[i] - EMA3[i - 1]) / EMA3[i - 1]

The triple smoothing strips out short-term noise so the resulting
momentum line oscillates around zero. Crossings of zero are the classic
trend-change cue.

Output length equals input length. Roughly ``3 * period - 3`` leading
positions are ``None`` (one ``None`` per nested EMA seed plus one for
the rate-of-change difference).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``3 * period > len(values) + 2`` (insufficient bars to seed three
      EMAs and take the rate of change) -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def trix(values: Sequence[float], period: int = 15) -> list[float | None]:
    """Triple-smoothed EMA momentum, expressed as a percent rate of change."""
    _check_period(period)
    n = len(values)
    if n == 0:
        return []

    e1 = ema(values, period)
    if not e1:
        return []
    # Strip the leading ``None`` block before re-feeding into ema(); the
    # nested EMAs are defined only over the part of e1 that has values.
    e1_defined = [v for v in e1 if v is not None]
    e1_offset = e1.index(e1_defined[0]) if e1_defined else 0

    e2_tail = ema(e1_defined, period)
    if not e2_tail:
        return [None] * n
    e2_defined_tail = [v for v in e2_tail if v is not None]
    if not e2_defined_tail:
        return [None] * n
    e2_offset_within_tail = e2_tail.index(e2_defined_tail[0])
    e2_offset = e1_offset + e2_offset_within_tail

    e3_tail = ema(e2_defined_tail, period)
    if not e3_tail:
        return [None] * n
    e3_defined_tail = [v for v in e3_tail if v is not None]
    if len(e3_defined_tail) < 2:
        return [None] * n
    e3_offset_within_tail = e3_tail.index(e3_defined_tail[0])
    e3_offset = e2_offset + e3_offset_within_tail

    out: list[float | None] = [None] * n
    # First defined TRIX is at e3_offset + 1 (need a previous value to
    # take the rate of change).
    for k in range(1, len(e3_defined_tail)):
        prev = e3_defined_tail[k - 1]
        cur = e3_defined_tail[k]
        if prev == 0:
            out[e3_offset + k] = 0.0
        else:
            out[e3_offset + k] = 100.0 * (cur - prev) / prev
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["trix"]
