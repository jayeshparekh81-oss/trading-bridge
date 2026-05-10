"""Rate-of-Change applied to volume rather than price.

Definition::

    ROC_V[i] = (volume[i] - volume[i - period]) / volume[i - period] * 100

Useful as a confirmation filter for price moves — a real
breakout typically shows a positive ROC of volume too.

Default ``period = 14``.

Output length equals input length. Indices ``0 .. period - 1``
are ``None``.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
    * volume[i - period] == 0 -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def rate_of_change_volume(
    volumes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """ROC of the volume series."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(volumes)
    if n == 0 or period >= n:
        return []
    out: list[float | None] = [None] * n
    for i in range(period, n):
        prev = volumes[i - period]
        if prev == 0:
            continue
        out[i] = (volumes[i] - prev) / prev * 100.0
    return out


__all__ = ["rate_of_change_volume"]
