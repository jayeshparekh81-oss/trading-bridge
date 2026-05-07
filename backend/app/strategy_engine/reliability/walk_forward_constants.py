"""Locked constants for the walk-forward analyser.

Single tunable knobs for window count, the per-window minimum bar
count, the consistency-score weights, and the verdict-band lower
bounds. Keep this module dependency-free.
"""

from __future__ import annotations

from typing import Final

DEFAULT_NUM_WINDOWS: Final[int] = 5
"""Default number of equal-sized segments the candle stream is sliced
into. Producing K-1 test windows (the first segment is training-only
on the anchored expanding-train schedule)."""

MIN_BARS_PER_WINDOW: Final[int] = 20
"""Minimum bar count per segment. Below this the test windows are
statistically meaningless; the analyser returns an empty report
instead of inventing a verdict."""

PROFITABLE_PCT_WEIGHT: Final[float] = 0.6
"""Weight on the "fraction of profitable test windows" component of
the consistency score."""

VARIANCE_WEIGHT: Final[float] = 0.4
"""Weight on the "P&L variance is low" component of the consistency
score. ``PROFITABLE_PCT_WEIGHT + VARIANCE_WEIGHT`` must equal 1.0."""

VARIANCE_PENALTY_PER_UNIT: Final[float] = 25.0
"""How aggressively variance reduces the variance sub-score:
``variance_score = max(0, 100 - pnl_variance_ratio * 25)``. A
coefficient of variation of 1.0 → score 75; 4.0 → score 0."""

VERDICT_THRESHOLDS: Final[dict[str, float]] = {
    "excellent": 80.0,
    "good": 65.0,
    "acceptable": 50.0,
}
"""Lower bounds (inclusive) for each verdict band. Anything below
``VERDICT_THRESHOLDS["acceptable"]`` is verdict ``"poor"``."""


__all__ = [
    "DEFAULT_NUM_WINDOWS",
    "MIN_BARS_PER_WINDOW",
    "PROFITABLE_PCT_WEIGHT",
    "VARIANCE_PENALTY_PER_UNIT",
    "VARIANCE_WEIGHT",
    "VERDICT_THRESHOLDS",
]
