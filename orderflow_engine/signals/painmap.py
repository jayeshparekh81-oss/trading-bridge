"""Pain-map lens (Module R6) — the Rothschild input, INERT (weight 0) by default.

Hypothesis (documented in TAPE_NOTES): trapped traders fuel the move that forces
their exit. Trapped LONGS (long_buildup gone offside, plus long_unwinding already
bailing) must SELL → downside fuel (short pressure). Trapped SHORTS (short_buildup
offside, plus short_covering) must BUY → upside fuel (long pressure). Max-pain acts
as a magnet: price far from max pain tends to be pulled toward it into expiry.

Returns a trapped-trader pressure in [0, 1] favouring ``side``. Computed + logged,
but contributes 0 to the score until its weight is raised post-calibration.
"""

from __future__ import annotations


def trapped_pressure(ctx, side: str) -> float:
    m = ctx.buildup_matrix or {}
    total = sum(m.values())
    base = 0.0
    if total > 0:
        if side == "long":
            fuel = m.get("short_buildup", 0) + m.get("short_covering", 0)
        else:
            fuel = m.get("long_buildup", 0) + m.get("long_unwinding", 0)
        base = fuel / total
    # max-pain magnet: nudge the side that points toward max pain
    if ctx.max_pain is not None and ctx.price:
        toward = (side == "long" and ctx.price < ctx.max_pain) or \
                 (side == "short" and ctx.price > ctx.max_pain)
        if toward:
            base = base + 0.1 * (1.0 - base)
    return max(0.0, min(1.0, base))
