"""On-Balance Volume — running flow tally driven by close-to-close direction.

Definition (Granville's original; matches Pine ``ta.obv``):

    OBV[0] = 0
    OBV[i] = OBV[i - 1] + volume[i]   if close[i] > close[i - 1]
           = OBV[i - 1] - volume[i]   if close[i] < close[i - 1]
           = OBV[i - 1]               if close[i] == close[i - 1]

Output length equals input length; OBV is defined at every bar (no warm-up).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def obv(closes: Sequence[float], volumes: Sequence[float]) -> list[float | None]:
    """On-balance volume."""
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n} and {len(volumes)}."
        )
    if n == 0:
        return []

    # Internal accumulator is float-only (no None positions in OBV); we
    # keep a parallel ``running`` to feed the recursion without paying
    # an Optional-narrowing cost at every step. The returned list type is
    # ``float | None`` to keep the indicator-output contract uniform.
    running = 0.0
    out: list[float | None] = [running]
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            running += volumes[i]
        elif closes[i] < closes[i - 1]:
            running -= volumes[i]
        out.append(running)
    return out


__all__ = ["obv"]
