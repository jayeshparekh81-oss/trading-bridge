"""Average Directional Index + Directional Movement Indicators (Wilder).

The single :func:`adx` function returns ``(adx, +DI, -DI)`` because the
three series share an expensive smoothing pipeline. Two registry
entries (``adx`` and ``dmi``) point at this same calculation; callers
read whichever output they want from the returned tuple.

Definition (Wilder, 1978; matches Pine ``ta.dmi`` / ``ta.adx``):

    True range and directional move (i >= 1)::
        TR     = max(high - low, |high - prev_close|, |low - prev_close|)
        upMove   = high[i] - high[i - 1]
        downMove = low[i - 1] - low[i]
        +DM    = upMove   if upMove > downMove and upMove > 0   else 0
        -DM    = downMove if downMove > upMove and downMove > 0 else 0

    Wilder smoothing of TR / +DM / -DM (period -> seed=sum, then
    next = prev * (period - 1) / period + current).

    +DI = 100 * smoothed_+DM / smoothed_TR
    -DI = 100 * smoothed_-DM / smoothed_TR
    DX  = 100 * |+DI - -DI| / (+DI + -DI)
    ADX = Wilder smoothing of DX over `period`.

Output length parity:
    Each returned list has ``len(highs)`` elements. ``+DI / -DI`` are
    defined from index ``period`` onward (sum-seeded smoothing); ``ADX``
    additionally needs ``period`` more bars for its own seed and is
    defined from index ``2 * period - 1`` onward.

Edge cases per Phase 1 contract:
    * Empty input or mismatched lengths -> ``[]`` (mismatch -> ValueError).
    * ``period * 2 > len(highs)`` -> ADX cannot seed; the +DI / -DI
      series may still seed if ``period < len(highs)``. Non-seeded
      positions are ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return ``(adx_line, plus_di_line, minus_di_line)``."""
    _check_period(period)
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return [], [], []

    plus_di: list[float | None] = [None] * n
    minus_di: list[float | None] = [None] * n
    adx_out: list[float | None] = [None] * n

    # Bar 0 has no prior close — TR/+DM/-DM are ill-defined; use 0
    # placeholders so the smoothed sums begin from bar 1.
    tr = [0.0] * n
    pdm = [0.0] * n
    mdm = [0.0] * n
    for i in range(1, n):
        prev_close = closes[i - 1]
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        pdm[i] = up if (up > down and up > 0) else 0.0
        mdm[i] = down if (down > up and down > 0) else 0.0

    # Need at least `period` "live" bars (indices 1..period) to seed.
    if n <= period:
        return adx_out, plus_di, minus_di

    # Wilder seed at index `period`: sum of first `period` live values.
    smoothed_tr = sum(tr[1 : period + 1])
    smoothed_pdm = sum(pdm[1 : period + 1])
    smoothed_mdm = sum(mdm[1 : period + 1])

    if smoothed_tr > 0:
        plus_di[period] = 100.0 * smoothed_pdm / smoothed_tr
        minus_di[period] = 100.0 * smoothed_mdm / smoothed_tr
    else:
        plus_di[period] = 0.0
        minus_di[period] = 0.0

    dx_history: list[float] = [_dx(plus_di[period], minus_di[period])]

    for i in range(period + 1, n):
        smoothed_tr = smoothed_tr * (period - 1) / period + tr[i]
        smoothed_pdm = smoothed_pdm * (period - 1) / period + pdm[i]
        smoothed_mdm = smoothed_mdm * (period - 1) / period + mdm[i]
        if smoothed_tr > 0:
            plus_di[i] = 100.0 * smoothed_pdm / smoothed_tr
            minus_di[i] = 100.0 * smoothed_mdm / smoothed_tr
        else:
            plus_di[i] = 0.0
            minus_di[i] = 0.0
        dx_history.append(_dx(plus_di[i], minus_di[i]))

    # ADX needs another `period` DX values to seed — first defined at
    # index 2 * period - 1 + 1 = 2 * period (one period of DX history,
    # whose first value lives at index `period`).
    adx_seed_index = 2 * period
    if adx_seed_index > n:
        return adx_out, plus_di, minus_di

    adx_seed = sum(dx_history[:period]) / period
    adx_out[adx_seed_index - 1] = adx_seed
    prev_adx = adx_seed
    for offset, dx_value in enumerate(dx_history[period:], start=adx_seed_index):
        if offset >= n:
            break
        prev_adx = (prev_adx * (period - 1) + dx_value) / period
        adx_out[offset] = prev_adx

    return adx_out, plus_di, minus_di


def _dx(plus: float | None, minus: float | None) -> float:
    """Single-bar DX value. Returns 0 when either DI is None."""
    if plus is None or minus is None:
        return 0.0
    total = plus + minus
    if total == 0:
        return 0.0
    return 100.0 * abs(plus - minus) / total


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["adx"]
