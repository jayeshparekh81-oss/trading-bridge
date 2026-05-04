"""Candle-pattern tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.strategy_engine.engines.candle_pattern import detect_candle_pattern
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import CandlePattern

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _bar(o: float, h: float, low: float, c: float, v: float = 1000.0) -> Candle:
    return Candle(timestamp=T0, open=o, high=h, low=low, close=c, volume=v)


# ─── bullish / bearish ──────────────────────────────────────────────────


def test_bullish_pattern_when_close_above_open() -> None:
    assert detect_candle_pattern(CandlePattern.BULLISH, current=_bar(100, 110, 99, 108)) is True


def test_bearish_pattern_when_close_below_open() -> None:
    assert detect_candle_pattern(CandlePattern.BEARISH, current=_bar(110, 112, 99, 100)) is True


def test_bullish_false_on_doji() -> None:
    """Equal open and close is neither bullish nor bearish."""
    bar = _bar(100, 105, 95, 100)
    assert detect_candle_pattern(CandlePattern.BULLISH, current=bar) is False
    assert detect_candle_pattern(CandlePattern.BEARISH, current=bar) is False


# ─── doji ───────────────────────────────────────────────────────────────


def test_doji_when_body_under_ten_percent_of_range() -> None:
    # range = 10, body = 0.5 (5%)
    assert detect_candle_pattern(CandlePattern.DOJI, current=_bar(100.0, 105, 95, 100.5)) is True


def test_doji_false_when_body_too_large() -> None:
    # range = 10, body = 5 (50%)
    assert detect_candle_pattern(CandlePattern.DOJI, current=_bar(100, 105, 95, 105)) is False


def test_doji_zero_range_treated_as_doji() -> None:
    """A flat bar (high == low) has zero body by definition."""
    assert detect_candle_pattern(CandlePattern.DOJI, current=_bar(100, 100, 100, 100)) is True


# ─── hammer ─────────────────────────────────────────────────────────────


def test_hammer_long_lower_shadow_small_body_top() -> None:
    """Body 100->101 (1) at top, lower shadow 100->90 (10), upper shadow 101->101.5 (0.5)."""
    bar = _bar(o=100, h=101.5, low=90, c=101)
    # range = 11.5, body = 1 (~8.7%), lower = 10 (~87%), upper = 0.5 (~4.3%)
    assert detect_candle_pattern(CandlePattern.HAMMER, current=bar) is True


def test_hammer_false_when_upper_shadow_long() -> None:
    """Long upper shadow disqualifies hammer regardless of lower-shadow size."""
    bar = _bar(o=100, h=120, low=90, c=101)
    assert detect_candle_pattern(CandlePattern.HAMMER, current=bar) is False


def test_hammer_false_on_zero_range() -> None:
    assert detect_candle_pattern(CandlePattern.HAMMER, current=_bar(100, 100, 100, 100)) is False


# ─── shooting star ─────────────────────────────────────────────────────


def test_shooting_star_long_upper_shadow_small_body_bottom() -> None:
    bar = _bar(o=100, h=110, low=99.5, c=99.8)
    # range = 10.5, body = 0.2, upper = 10, lower = 0.3
    assert detect_candle_pattern(CandlePattern.SHOOTING_STAR, current=bar) is True


def test_shooting_star_false_when_lower_shadow_long() -> None:
    bar = _bar(o=100, h=110, low=80, c=101)
    assert detect_candle_pattern(CandlePattern.SHOOTING_STAR, current=bar) is False


# ─── engulfing ─────────────────────────────────────────────────────────


def test_bearish_engulfing_when_current_body_covers_prior_opposite_direction() -> None:
    prior = _bar(o=100, h=103, low=99, c=102)  # bullish 100..102
    current = _bar(o=103, h=104, low=98, c=99)  # bearish 99..103
    assert detect_candle_pattern(CandlePattern.ENGULFING, current=current, prior=prior) is True


def test_bullish_engulfing_when_current_body_covers_prior_opposite_direction() -> None:
    prior = _bar(o=102, h=103, low=99, c=100)  # bearish 100..102
    current = _bar(o=99, h=104, low=98.5, c=103)  # bullish 99..103
    assert detect_candle_pattern(CandlePattern.ENGULFING, current=current, prior=prior) is True


def test_engulfing_false_when_same_direction() -> None:
    """Two bullish bars with the second engulfing the first body — NOT engulfing."""
    prior = _bar(o=100, h=101, low=99.5, c=100.5)
    current = _bar(o=100.4, h=102, low=100, c=101)
    assert detect_candle_pattern(CandlePattern.ENGULFING, current=current, prior=prior) is False


def test_engulfing_false_when_body_does_not_engulf() -> None:
    prior = _bar(o=100, h=103, low=99, c=102)  # bullish 100..102
    current = _bar(o=101.5, h=102, low=99, c=100.5)  # bearish 100.5..101.5 — inside
    assert detect_candle_pattern(CandlePattern.ENGULFING, current=current, prior=prior) is False


def test_engulfing_false_when_no_prior_bar() -> None:
    bar = _bar(100, 110, 95, 105)
    assert detect_candle_pattern(CandlePattern.ENGULFING, current=bar, prior=None) is False
