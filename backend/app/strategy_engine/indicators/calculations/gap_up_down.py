"""Gap up / down classifier.

Per-bar code based on today's open vs prior bar's close:

    +1.0  → gap-up beyond ``threshold_pct`` (% of prior close)
    -1.0  → gap-down beyond ``threshold_pct``
     0.0  → no significant gap

Default ``threshold_pct = 0.5`` (half a percent — calibrated for
NIFTY-tier liquidity; bump higher for mid/small caps).

Output length equals input length. Index 0 is always ``None``
(no prior bar).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Prior close == 0 -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def gap_up_down(
    opens: Sequence[float],
    closes: Sequence[float],
    threshold_pct: float = 0.5,
) -> list[float | None]:
    """Per-bar gap-direction code."""
    if not isinstance(threshold_pct, (int, float)) or isinstance(threshold_pct, bool):
        raise ValueError(f"threshold_pct must be a number; got {threshold_pct!r}.")
    if threshold_pct < 0:
        raise ValueError(f"threshold_pct must be >= 0; got {threshold_pct}.")
    n = len(opens)
    if n != len(closes):
        raise ValueError(
            f"opens and closes must have the same length; got {n}, {len(closes)}."
        )
    if n == 0:
        return []
    out: list[float | None] = [None] * n
    for i in range(1, n):
        prev_close = closes[i - 1]
        if prev_close == 0:
            continue
        gap_pct = (opens[i] - prev_close) / prev_close * 100.0
        if gap_pct > threshold_pct:
            out[i] = 1.0
        elif gap_pct < -threshold_pct:
            out[i] = -1.0
        else:
            out[i] = 0.0
    return out


__all__ = ["gap_up_down"]
