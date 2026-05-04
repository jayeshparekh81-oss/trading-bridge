"""Candle-pattern primitives — pure single- / two-bar predicates.

Each pattern is implemented as a deterministic boolean test on the
current candle (and prior candle for two-bar patterns). Thresholds are
deliberately conservative — the goal is "obvious examples of the
pattern", not literature-perfect detection. The Phase 6 advisor and
Phase 9 indicator-expansion can layer more nuance on top later.

Patterns supported:

    bullish              close > open
    bearish              close < open
    engulfing            two-bar; current body fully covers prior body and
                         current is the opposite direction of prior
    doji                 |close - open| <= 10 % of (high - low)
    hammer               small upper shadow + long lower shadow + body in
                         upper third
    shooting_star        long upper shadow + small lower shadow + body in
                         lower third

Two breakout primitives are also routed through this module so the
caller has one entry point for "candle-shape" tests:

    previous_high_breakout    current.high > prior.high
    previous_low_breakdown    current.low  < prior.low

Patterns that require a prior bar (engulfing + breakouts) return
``False`` when ``prior is None`` rather than raising — strategies that
fire on the first bar of data shouldn't crash, they just don't match.
"""

from __future__ import annotations

from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import CandlePattern


def detect_candle_pattern(
    pattern: CandlePattern,
    *,
    current: Candle,
    prior: Candle | None = None,
) -> bool:
    """Return True iff ``current`` (and ``prior`` for two-bar patterns)
    matches the requested ``pattern``.
    """
    if pattern is CandlePattern.BULLISH:
        return current.close > current.open
    if pattern is CandlePattern.BEARISH:
        return current.close < current.open
    if pattern is CandlePattern.DOJI:
        return _is_doji(current)
    if pattern is CandlePattern.HAMMER:
        return _is_hammer(current)
    if pattern is CandlePattern.SHOOTING_STAR:
        return _is_shooting_star(current)
    if pattern is CandlePattern.ENGULFING:
        if prior is None:
            return False
        return _is_engulfing(current=current, prior=prior)
    raise ValueError(  # pragma: no cover — unreachable if CandlePattern is exhaustive
        f"Unhandled CandlePattern: {pattern!r}"
    )


# ─── Single-bar helpers ────────────────────────────────────────────────


#: Doji body tolerance — body must be <= this fraction of the candle range.
_DOJI_BODY_RATIO = 0.10

#: Hammer / shooting-star — body must be <= this fraction of the range
#: AND the dominant shadow must be >= this fraction of the range.
_HAMMER_BODY_RATIO = 0.30
_HAMMER_SHADOW_RATIO = 0.60


def _is_doji(c: Candle) -> bool:
    rng = c.high - c.low
    if rng <= 0:
        # No range at all — every price equal. Treat as a doji (zero body).
        return True
    body = abs(c.close - c.open)
    return body <= rng * _DOJI_BODY_RATIO


def _is_hammer(c: Candle) -> bool:
    """Small body in the upper third + long lower shadow.

    Standard charting definition: lower shadow >= 60 % of total range,
    body <= 30 % of total range, upper shadow short. Body direction (red
    vs green) is allowed either way — context (uptrend / downtrend) is
    the strategy's job, not this predicate's.
    """
    rng = c.high - c.low
    if rng <= 0:
        return False
    body_top = max(c.open, c.close)
    body_bottom = min(c.open, c.close)
    body = body_top - body_bottom
    upper_shadow = c.high - body_top
    lower_shadow = body_bottom - c.low

    return (
        body <= rng * _HAMMER_BODY_RATIO
        and lower_shadow >= rng * _HAMMER_SHADOW_RATIO
        and upper_shadow <= lower_shadow * 0.5
    )


def _is_shooting_star(c: Candle) -> bool:
    """Mirror image of hammer — body in lower third, long upper shadow."""
    rng = c.high - c.low
    if rng <= 0:
        return False
    body_top = max(c.open, c.close)
    body_bottom = min(c.open, c.close)
    body = body_top - body_bottom
    upper_shadow = c.high - body_top
    lower_shadow = body_bottom - c.low

    return (
        body <= rng * _HAMMER_BODY_RATIO
        and upper_shadow >= rng * _HAMMER_SHADOW_RATIO
        and lower_shadow <= upper_shadow * 0.5
    )


# ─── Two-bar helper ────────────────────────────────────────────────────


def _is_engulfing(*, current: Candle, prior: Candle) -> bool:
    """Bullish OR bearish engulfing — direction-agnostic.

    Body of ``current`` must fully cover the body of ``prior`` AND the
    two bars must be of opposite direction (one bullish, one bearish).
    Equal-direction "outside bars" do not count.
    """
    prior_body_top = max(prior.open, prior.close)
    prior_body_bottom = min(prior.open, prior.close)
    current_body_top = max(current.open, current.close)
    current_body_bottom = min(current.open, current.close)

    body_engulfs = current_body_bottom <= prior_body_bottom and current_body_top >= prior_body_top
    if not body_engulfs:
        return False

    prior_dir = _bar_direction(prior)
    current_dir = _bar_direction(current)
    # Both directions must be defined (non-doji) AND opposite.
    return prior_dir != 0 and current_dir != 0 and prior_dir != current_dir


def _bar_direction(c: Candle) -> int:
    """+1 for bullish, -1 for bearish, 0 for flat (close == open)."""
    if c.close > c.open:
        return 1
    if c.close < c.open:
        return -1
    return 0


__all__ = ["detect_candle_pattern"]
