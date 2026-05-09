"""Three Black Crows candlestick pattern (three-bar bearish).

Mirror of :mod:`three_white_soldiers`.

Definition:

    For k in (i-2, i-1, i):
        close[k] < open[k]                    (bearish)
        body[k] / range[k] >= min_body_ratio  (default 0.5)

    Plus:
        close[i-1] < close[i-2]                (falling closes)
        close[i]   < close[i-1]
        opens[i-1] inside (close[i-2], open[i-2])
        opens[i]   inside (close[i-1], open[i-1])
"""

from __future__ import annotations

from collections.abc import Sequence


def three_black_crows(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    min_body_ratio: float = 0.5,
) -> list[float | None]:
    """Detect three-black-crows sequences."""
    if not (0 < min_body_ratio < 1):
        raise ValueError(
            f"min_body_ratio must be in (0, 1); got {min_body_ratio!r}."
        )
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [None, None] + [0.0] * (n - 2) if n >= 2 else [None] * n
    for i in range(2, n):
        ok = True
        for k in (i - 2, i - 1, i):
            rng = highs[k] - lows[k]
            if rng <= 0:
                ok = False
                break
            if closes[k] >= opens[k]:
                ok = False
                break
            body = opens[k] - closes[k]
            if body < rng * min_body_ratio:
                ok = False
                break
        if not ok:
            continue
        if closes[i - 1] >= closes[i - 2] or closes[i] >= closes[i - 1]:
            continue
        if not (closes[i - 2] <= opens[i - 1] <= opens[i - 2]):
            continue
        if not (closes[i - 1] <= opens[i] <= opens[i - 1]):
            continue
        out[i] = 1.0
    return out


def _check_lengths(*series: Sequence[float]) -> int:
    n = len(series[0])
    for s in series[1:]:
        if len(s) != n:
            raise ValueError(
                f"OHLC series must have the same length; got "
                f"{[len(x) for x in series]}."
            )
    return n


__all__ = ["three_black_crows"]
