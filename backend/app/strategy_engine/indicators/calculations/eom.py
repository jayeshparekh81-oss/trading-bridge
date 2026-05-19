"""Ease of Movement (EOM) — Pine ``ta.eom`` parity.

Richard Arms' EOM (1980s) — measures how easily price moves relative
to the volume traded. Big midpoint moves on small volume produce high
EOM (price was easy to push); small midpoint moves on large volume
produce low EOM (heavy volume pinning price).

Definition (matches Pine ``ta.eom(length, divisor)``):
    midpoint_move[i] = (high[i] + low[i]) / 2
                     - (high[i-1] + low[i-1]) / 2          (None at i=0)
    box_ratio[i]     = (volume[i] / divisor) / (high[i] - low[i])
    eom_raw[i]       = midpoint_move[i] / box_ratio[i]
    EOM[i]           = SMA(eom_raw, length)[i]

    Default ``length = 14``, ``divisor = 10000`` (Pine's defaults).
    First defined index = length (one extra warm-up for the diff seed).

Guards:
    * high[i] == low[i] (zero-range bar) → box_ratio infinite/zero → None
    * volume[i] == 0 → box_ratio = 0 → eom_raw infinite/undefined → None

Source: Pine v5 ``ta.eom``; Richard Arms, "Ease of Movement" original
publication (1980s).

Edge cases:
    * Empty / length-mismatch -> ``[]`` / ``ValueError``
    * ``length > n - 1`` (need at least length+1 bars) -> ``[]``
    * Invalid length/divisor -> ``ValueError``
"""

from __future__ import annotations

from collections.abc import Sequence


def eom(
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
    length: int = 14,
    divisor: int = 10000,
) -> list[float | None]:
    """Richard Arms' Ease of Movement — Pine ``ta.eom`` parity."""
    _check_period(length, "length")
    if not isinstance(divisor, int) or isinstance(divisor, bool) or divisor <= 0:
        raise ValueError(f"divisor must be a positive int; got {divisor!r}.")
    n = len(highs)
    if n != len(lows) or n != len(volumes):
        raise ValueError(
            f"highs, lows, volumes must all have same length; "
            f"got {n}, {len(lows)}, {len(volumes)}."
        )
    if n == 0 or length > n - 1:
        return []

    # Build raw EOM series (None at index 0; possibly None elsewhere for
    # zero-range bars).
    eom_raw: list[float | None] = [None]
    for i in range(1, n):
        h, l, v = float(highs[i]), float(lows[i]), float(volumes[i])
        h_prev, l_prev = float(highs[i - 1]), float(lows[i - 1])
        midpoint_move = (h + l) / 2.0 - (h_prev + l_prev) / 2.0
        rng = h - l
        if rng == 0.0:
            eom_raw.append(None)
            continue
        box_ratio = (v / divisor) / rng
        if box_ratio == 0.0:
            eom_raw.append(None)
            continue
        eom_raw.append(midpoint_move / box_ratio)

    # SMA over eom_raw with ``length`` window. The window must contain
    # length non-None values; if ANY None falls in the window, the SMA
    # is None for that bar.
    out: list[float | None] = [None] * n
    for i in range(length, n):
        window = eom_raw[i - length + 1 : i + 1]
        if any(v is None for v in window):
            out[i] = None
        else:
            out[i] = sum(window) / length  # type: ignore[arg-type]
    return out


def _check_period(period: int, name: str) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"{name} must be a positive int; got {period!r}.")


__all__ = ["eom"]
