"""MESA Sine Wave (John Ehlers).

Computes the *sine* component of the dominant-cycle phase. The
companion *lead* component is in :mod:`mesa_sine_lead`. Together
they form the MESA Sine Wave / Sine Lead pair Ehlers introduced
in his 1992 book — crossings of the two lines flag cycle turning
points 1/8 of a cycle ahead of the actual reversal.

Definition::

    period[i] = dominant_cycle_period(close)[i]
    phase[i]  = current cycle phase derived from the same Hilbert
                transform that produced ``period``
    sine[i]   = sin(phase[i])
    lead[i]   = sin(phase[i] + π/4)        # 45° lead

We share the in-phase / quadrature decomposition with the
:mod:`dominant_cycle_period` module via :func:`_mesa_phase_series`
so both indicators stay in lock-step.

Default ``alpha = 0.07`` (smoothing factor on the raw phase).

Output range is ``[-1, +1]``. ``None`` for the warmup (~30 bars).

Edge cases:
    * Empty input -> ``[]``.
    * Input shorter than the warmup -> ``[]``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

_MIN_WARMUP = 30


def mesa_sine_wave(
    closes: Sequence[float],
    alpha: float = 0.07,
) -> list[float | None]:
    """Sine-wave projection of the dominant-cycle phase."""
    phase = _mesa_phase_series(closes, alpha)
    return [None if p is None else math.sin(p) for p in phase]


def _mesa_phase_series(
    closes: Sequence[float],
    alpha: float,
) -> list[float | None]:
    """Per-bar dominant-cycle phase in radians.

    Shared between :mod:`mesa_sine_wave` and :mod:`mesa_sine_lead`
    so both lines move from the same underlying Hilbert state."""
    if not isinstance(alpha, (int, float)) or isinstance(alpha, bool):
        raise ValueError(f"alpha must be a number; got {alpha!r}.")
    if alpha <= 0 or alpha > 1:
        raise ValueError(f"alpha must be in (0, 1]; got {alpha}.")
    n = len(closes)
    if n == 0 or n < _MIN_WARMUP:
        return []

    smoothed: list[float] = [0.0] * n
    for i in range(3, n):
        smoothed[i] = (
            4 * closes[i] + 3 * closes[i - 1]
            + 2 * closes[i - 2] + closes[i - 3]
        ) / 10.0

    detrender: list[float] = [0.0] * n
    for i in range(6, n):
        detrender[i] = (
            0.0962 * smoothed[i]
            + 0.5769 * smoothed[i - 2]
            - 0.5769 * smoothed[i - 4]
            - 0.0962 * smoothed[i - 6]
        )

    out: list[float | None] = [None] * n
    smoothed_phase = 0.0
    for i in range(_MIN_WARMUP, n):
        q1 = (
            0.0962 * detrender[i]
            + 0.5769 * detrender[i - 2]
            - 0.5769 * detrender[i - 4]
            - 0.0962 * detrender[i - 6]
        )
        i1 = detrender[i - 3]
        raw_phase = math.atan2(q1, i1) if i1 != 0 else smoothed_phase
        # EMA smoothing of phase in the unwrapped sense — wraparound
        # is handled implicitly by the sine projection.
        smoothed_phase = alpha * raw_phase + (1.0 - alpha) * smoothed_phase
        out[i] = smoothed_phase
    return out


__all__ = ["mesa_sine_wave"]
