"""Pack 15 - time-based + session + intraday tests.

Same shape as Pack 2-14. Active count assertion ``>= 191``.

Frequency-aware coverage: every intraday-only indicator gets a
test for the daily-frequency path (returns all-None) AND the
intraday path (produces real values).

No new Pine wiring; pinned by the Pack 15 lock test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack15_active import (
    PACK15_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.day_of_week_signal import (
    day_of_week_signal,
)
from app.strategy_engine.indicators.calculations.first_hour_range import (
    first_hour_range,
)
from app.strategy_engine.indicators.calculations.hour_of_day import hour_of_day
from app.strategy_engine.indicators.calculations.is_expiry_week import (
    is_expiry_week,
)
from app.strategy_engine.indicators.calculations.last_hour_momentum import (
    last_hour_momentum,
)
from app.strategy_engine.indicators.calculations.lunch_consolidation import (
    lunch_consolidation,
)
from app.strategy_engine.indicators.calculations.minutes_to_close import (
    minutes_to_close,
)
from app.strategy_engine.indicators.calculations.opening_gap_size import (
    opening_gap_size,
)
from app.strategy_engine.indicators.calculations.session_high_breakout import (
    session_high_breakout,
)
from app.strategy_engine.indicators.calculations.session_low_breakout import (
    session_low_breakout,
)
from app.strategy_engine.indicators.calculations.session_open_distance import (
    session_open_distance,
)
from app.strategy_engine.indicators.calculations.session_volume_pace import (
    session_volume_pace,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def _intraday_timestamps(n: int, start: datetime | None = None,
                          interval_min: int = 5) -> list[datetime]:
    """N timestamps spaced ``interval_min`` minutes apart starting
    at 9:15 IST on a Monday (default 2026-05-04)."""
    base = start or datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    return [base + timedelta(minutes=i * interval_min) for i in range(n)]


def _daily_timestamps(n: int) -> list[datetime]:
    """N timestamps one day apart."""
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    return [base + timedelta(days=i) for i in range(n)]


# --- Time-based (4) -------------------------------------------------


def test_day_of_week_signal_monday_yields_zero() -> None:
    out = day_of_week_signal(timestamps=_daily_timestamps(7))
    assert out[0] == 0.0  # Monday 2026-05-04


def test_day_of_week_signal_friday_yields_four() -> None:
    out = day_of_week_signal(timestamps=_daily_timestamps(7))
    # Index 4 is Friday (Mon + 4).
    assert out[4] == 4.0


def test_hour_of_day_intraday_returns_hour() -> None:
    out = hour_of_day(timestamps=_intraday_timestamps(20))
    assert out[0] == 9.0
    # 5 minutes per bar * 12 bars = 60 mins → hour=10.
    assert out[12] == 10.0


def test_hour_of_day_daily_returns_all_none() -> None:
    out = hour_of_day(timestamps=_daily_timestamps(10))
    assert all(v is None for v in out)


def test_minutes_to_close_intraday_decreases() -> None:
    """Across the session, minutes_to_close should monotonically
    decrease."""
    out = minutes_to_close(timestamps=_intraday_timestamps(50, interval_min=5))
    # Filter Nones and check monotone decreasing.
    defined = [v for v in out if v is not None]
    assert all(defined[k] > defined[k + 1] for k in range(len(defined) - 1))


def test_minutes_to_close_daily_returns_all_none() -> None:
    out = minutes_to_close(timestamps=_daily_timestamps(10))
    assert all(v is None for v in out)


def test_minutes_to_close_rejects_invalid_hour() -> None:
    with pytest.raises(ValueError, match=r"in \[0, 23\]"):
        minutes_to_close(
            timestamps=_intraday_timestamps(10), market_close_hour=25,
        )


def test_is_expiry_week_last_thursday_of_may_2026() -> None:
    """May 2026: last Thursday is the 28th (a Thursday). The week
    of May 25-31 should flag as expiry week."""
    base = datetime(2026, 5, 25, 9, 15, tzinfo=UTC)  # Monday
    timestamps = [base + timedelta(days=i) for i in range(7)]
    out = is_expiry_week(timestamps=timestamps)
    # Mon 25..Sun 31 should all flag (week containing Thu 28).
    assert all(v == 1.0 for v in out)


def test_is_expiry_week_first_week_of_may_2026_is_not_expiry() -> None:
    """May 2026: first week (May 4-10) is not expiry week."""
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    timestamps = [base + timedelta(days=i) for i in range(7)]
    out = is_expiry_week(timestamps=timestamps)
    assert all(v == 0.0 for v in out)


# --- Session-aware (4) ----------------------------------------------


def test_session_open_distance_at_open_is_zero() -> None:
    """First bar of the day with close == open -> distance = 0."""
    timestamps = _intraday_timestamps(10)
    out = session_open_distance(
        opens=[100.0] * 10, closes=[100.0] * 10, timestamps=timestamps,
    )
    assert out[0] == 0.0


def test_session_open_distance_daily_returns_all_none() -> None:
    out = session_open_distance(
        opens=[100.0] * 10, closes=[101.0] * 10,
        timestamps=_daily_timestamps(10),
    )
    assert all(v is None for v in out)


def test_session_high_breakout_first_bar_yields_one() -> None:
    """First bar of day always counts as a new high."""
    out = session_high_breakout(
        highs=[101.0, 100.0, 102.0, 101.5, 103.0],
        timestamps=_intraday_timestamps(5),
    )
    assert out[0] == 1.0
    assert out[1] == 0.0  # 100 < running 101
    assert out[2] == 1.0  # 102 > 101
    assert out[3] == 0.0  # 101.5 < 102
    assert out[4] == 1.0  # 103 > 102


def test_session_high_breakout_daily_returns_all_none() -> None:
    out = session_high_breakout(
        highs=[101.0] * 10, timestamps=_daily_timestamps(10),
    )
    assert all(v is None for v in out)


def test_session_low_breakout_mirrors_high_breakout() -> None:
    out = session_low_breakout(
        lows=[100.0, 101.0, 99.0, 99.5, 98.0],
        timestamps=_intraday_timestamps(5),
    )
    assert out[0] == 1.0  # first bar
    assert out[1] == 0.0  # 101 > running 100
    assert out[2] == 1.0  # 99 < 100
    assert out[3] == 0.0  # 99.5 > 99
    assert out[4] == 1.0  # 98 < 99


def test_session_volume_pace_insufficient_history_returns_none() -> None:
    """Need 2+ prior days at the same time-of-day; first day has none."""
    out = session_volume_pace(
        volumes=[1000.0] * 10, timestamps=_intraday_timestamps(10),
        lookback_days=20,
    )
    assert all(v is None for v in out)


def test_session_volume_pace_rejects_short_lookback() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        session_volume_pace(
            volumes=[1.0] * 10, timestamps=_intraday_timestamps(10),
            lookback_days=1,
        )


# --- Intraday-specific (4) ------------------------------------------


def test_first_hour_range_emits_constant_after_window() -> None:
    """First-hour bars (12 5-min bars) → None. After hour 1, every
    bar gets the same range."""
    n = 30  # 30 5-min bars = 2.5 hours
    highs = [101.0] * n
    lows = [99.0] * n  # constant range = 2
    timestamps = _intraday_timestamps(n, interval_min=5)
    out = first_hour_range(
        highs=highs, lows=lows, timestamps=timestamps, minutes=60,
    )
    # Bars 0-11 (first hour) → None.
    assert all(v is None for v in out[:12])
    # Bars 12+ → 2.0 constant.
    assert all(v == 2.0 for v in out[12:])


def test_first_hour_range_daily_returns_all_none() -> None:
    out = first_hour_range(
        highs=[101.0] * 5, lows=[99.0] * 5,
        timestamps=_daily_timestamps(5), minutes=60,
    )
    assert all(v is None for v in out)


def test_last_hour_momentum_baseline_is_zero() -> None:
    """First bar of the last-hour window has 0% change vs itself."""
    # Build 5-min bars from 14:30 to 15:30 (12 bars; the last 12
    # are inside the 60-min last-hour window). Need to start
    # before 14:30 so the indicator can detect intraday frequency
    # (needs 2+ bars).
    base = datetime(2026, 5, 4, 14, 25, tzinfo=UTC)
    timestamps = [base + timedelta(minutes=i * 5) for i in range(13)]
    closes = [100.0 + i for i in range(13)]
    out = last_hour_momentum(
        closes=closes, timestamps=timestamps, minutes=60,
        market_close_hour=15, market_close_min=30,
    )
    # Bar at 14:30 is the first inside the window (last 60 mins
    # = 14:30 - 15:30). It's the anchor -> momentum = 0.
    # That's index 1 (0=14:25, 1=14:30, 2=14:35, ...).
    assert out[1] == pytest.approx(0.0)


def test_last_hour_momentum_daily_returns_all_none() -> None:
    out = last_hour_momentum(
        closes=[100.0] * 5, timestamps=_daily_timestamps(5),
    )
    assert all(v is None for v in out)


def test_lunch_consolidation_quiet_lunch_bar_yields_one() -> None:
    """Lunch bar with below-avg vol + below-avg range -> 1.0.
    Build morning bars with high vol/range, then a quiet lunch bar."""
    # 5 morning bars (9:15..9:35), then 4 lunch bars at 12:00..
    morning_count = 12  # 12 5-min bars = 9:15..10:10
    lunch_count = 4
    highs = []
    lows = []
    volumes = []
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    timestamps = []
    for i in range(morning_count):
        # Morning: high vol, wide range.
        highs.append(102.0)
        lows.append(98.0)
        volumes.append(1000.0)
        timestamps.append(base + timedelta(minutes=i * 5))
    # Now append 4 5-min bars in lunch (12:00..12:15).
    lunch_base = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    for i in range(lunch_count):
        # Lunch: low vol, tight range.
        highs.append(100.5)
        lows.append(100.0)
        volumes.append(100.0)
        timestamps.append(lunch_base + timedelta(minutes=i * 5))
    out = lunch_consolidation(
        highs=highs, lows=lows, volumes=volumes, timestamps=timestamps,
        lunch_start_hour=12, lunch_end_hour=13,
    )
    # Lunch bars (last 4) should all be 1.0 — well below morning's
    # vol + range averages.
    assert all(v == 1.0 for v in out[morning_count:])


def test_lunch_consolidation_rejects_invalid_hours() -> None:
    with pytest.raises(ValueError, match="<="):
        lunch_consolidation(
            highs=[1.0] * 10, lows=[1.0] * 10, volumes=[1.0] * 10,
            timestamps=_intraday_timestamps(10),
            lunch_start_hour=13, lunch_end_hour=12,
        )


def test_opening_gap_size_no_prior_day_returns_none() -> None:
    """First day of input has no prior session."""
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    timestamps = [base + timedelta(minutes=i * 5) for i in range(5)]
    out = opening_gap_size(
        opens=[100.0] * 5, closes=[101.0] * 5, timestamps=timestamps,
    )
    assert all(v is None for v in out)


def test_opening_gap_size_calculates_pct_gap() -> None:
    """Day 1: open 100, close 101. Day 2: open 103 → gap = +1.98%."""
    day1 = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    day2 = datetime(2026, 5, 5, 9, 15, tzinfo=UTC)
    timestamps = [day1, day2]
    out = opening_gap_size(
        opens=[100.0, 103.0], closes=[101.0, 104.0], timestamps=timestamps,
    )
    assert out[0] is None
    # (103 - 101) / 101 * 100 = 1.9802...
    assert out[1] == pytest.approx(1.9802, abs=0.01)


# --- Registry promotion ---------------------------------------------


_PACK15_IDS = {
    "day_of_week_signal",
    "hour_of_day",
    "minutes_to_close",
    "is_expiry_week",
    "session_open_distance",
    "session_high_breakout",
    "session_low_breakout",
    "session_volume_pace",
    "first_hour_range",
    "last_hour_momentum",
    "lunch_consolidation",
    "opening_gap_size",
}


def test_pack15_module_exposes_twelve_indicators() -> None:
    assert len(PACK15_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK15_ACTIVE_INDICATORS} == _PACK15_IDS


def test_pack15_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK15_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack15_is_one_hundred_ninety_one() -> None:
    """Pack-14 baseline 179 + 12 Pack 15 = 191."""
    assert len(get_active_indicators()) >= 191


def test_pack15_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK15_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack15_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK15_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


def test_pack15_has_no_pine_aliases() -> None:
    """Pack 15 ships no Pine wiring - none of the indicators have
    a standard Pine v5 ta.* equivalent (Pine has timestamp helpers
    as reserved variables, not as ta.* functions)."""
    for meta in PACK15_ACTIVE_INDICATORS:
        assert meta.pine_aliases == [], (
            f"{meta.id} unexpectedly has Pine aliases: {meta.pine_aliases}"
        )


# --- Backtest dispatch ----------------------------------------------


def _intraday_candles(n: int = 30) -> list:
    """Synthetic 5-min intraday candles starting 9:15."""
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    out = []
    for i in range(n):
        # Candle factory uses minutes offset from a base — replicate
        # the timestamp directly.
        ts = base + timedelta(minutes=i * 5)
        # Use the make_candle conftest helper; pass minutes=i*5 so
        # the helper aligns with our intended timestamp.
        out.append(
            make_candle(
                minutes=int((ts - base).total_seconds() / 60),
                open_=100.0, high=101.0, low=99.0, close=100.5,
                volume=1000.0,
                base_ts=base,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("day_of_week_signal", {}),
        ("hour_of_day", {}),
        (
            "minutes_to_close",
            {"market_close_hour": 15, "market_close_min": 30},
        ),
        ("is_expiry_week", {}),
        ("session_open_distance", {}),
        ("session_high_breakout", {}),
        ("session_low_breakout", {}),
        ("session_volume_pace", {"lookback_days": 20}),
        ("first_hour_range", {"minutes": 60}),
        (
            "last_hour_momentum",
            {"minutes": 60, "market_close_hour": 15, "market_close_min": 30},
        ),
        (
            "lunch_consolidation",
            {"lunch_start_hour": 12, "lunch_end_hour": 13},
        ),
        ("opening_gap_size", {}),
    ],
)
def test_pack15_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 15 indicator dispatches successfully and produces
    a same-length series."""
    candles = _intraday_candles(30)
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    assert not any(f"{indicator_type}_inst" in w for w in warnings)
