"""Pack 15 - 12 time-based + session + intraday indicators.

No discovery-time collisions on indicator ids. Pack 8 already
shipped four timestamp-aware indicators (gap_up_down,
opening_range_breakout, weekly_pivot_close,
daily_pivot_distance) — Pack 15 adds twelve more from a
different angle:

    * day_of_week_signal / hour_of_day / minutes_to_close /
      is_expiry_week — direct timestamp projections + Indian-
      F&O-month context.
    * session_open_distance / session_high_breakout /
      session_low_breakout / session_volume_pace — intraday
      session-relative measures.
    * first_hour_range / last_hour_momentum / lunch_consolidation
      / opening_gap_size — specific intraday windows.

Pack 15's ``opening_gap_size`` (continuous %) coexists with
Pack 8's ``gap_up_down`` (discrete +1 / 0 / -1 classifier).
Same input, different output shape — both useful.

NO new Pine importer wiring - none of Pack 15's indicators
have a standard Pine v5 ``ta.*`` equivalent (Pine has
timestamp helpers like ``time()``, ``dayofweek``, ``hour`` as
reserved variables, not ``ta.*`` functions). Lock test
``test_pack15_has_no_pine_aliases`` pins the contract.

Frequency-aware: every Pack 15 indicator that requires intraday
data detects the bar frequency by inspecting the gap between the
first two timestamps. If gap >= 24 hours, returns all-``None``.
``day_of_week_signal``, ``is_expiry_week``, and
``opening_gap_size`` work at any frequency (daily-or-larger
included) since they only need the date.

Honest scope notes:

* ``is_expiry_week`` flags the calendar week containing the
  *last Thursday of the month* (Indian F&O monthly expiry). Does
  NOT flag weekly-options expiries; weekly expiry weekday has
  changed multiple times for Bank Nifty / Nifty in recent years
  and would need exchange-symbol context the calc layer doesn't
  have.
* ``session_volume_pace`` needs at least 2 prior days at the
  same time-of-day to form a typical-pace baseline; bars where
  that history isn't available return ``None``.
* All timestamps are assumed naive-or-IST. Tz-aware UTC
  timestamps land in the wrong hour bucket — operator should
  pre-normalise before feeding the calc layer.

Difficulty split (BEGINNER/INTERMEDIATE/EXPERT - schema has
no ADVANCED tier; spec's "ADVANCED" mapped to EXPERT):

    INTERMEDIATE (6) - day_of_week_signal, hour_of_day,
                       opening_gap_size, session_open_distance,
                       session_high_breakout, session_low_breakout
    EXPERT (6)       - minutes_to_close, is_expiry_week,
                       session_volume_pace, first_hour_range,
                       last_hour_momentum, lunch_consolidation
"""

from __future__ import annotations

from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
    InputSpec,
    InputType,
)

# --- Time-based (4) -------------------------------------------------


_DAY_OF_WEEK_SIGNAL = IndicatorMetadata(
    id="day_of_week_signal",
    name="Day-of-Week Signal",
    category="Time",
    description=(
        "0 (Mon) through 6 (Sun) per bar. Day-of-week effect "
        "filter — strategies that want to favour Tue/Wed and "
        "fade Friday afternoons."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Day of Week = bar ka weekday (0=Mon..6=Sun). Day-of-week "
        "effect strategies ke liye filter."
    ),
    tags=["time", "calendar"],
    calculation_function="day_of_week_signal",
)


_HOUR_OF_DAY = IndicatorMetadata(
    id="hour_of_day",
    name="Hour of Day",
    category="Time",
    description=(
        "0..23 hour from intraday timestamp. Returns all-None on "
        "daily-or-larger candle frequencies."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Hour of Day = bar ka hour (0-23). Intraday strategies "
        "ke liye session-of-day filter (avoid open/close volatility)."
    ),
    tags=["time", "intraday"],
    calculation_function="hour_of_day",
)


_MINUTES_TO_CLOSE = IndicatorMetadata(
    id="minutes_to_close",
    name="Minutes to Close",
    category="Time",
    description=(
        "Minutes from each intraday bar's timestamp to the day's "
        "market close (default 15:30 IST). Useful for last-N-"
        "minute exit logic."
    ),
    inputs=[
        InputSpec(name="market_close_hour", type=InputType.NUMBER, default=15, min=0, max=23),
        InputSpec(name="market_close_min", type=InputType.NUMBER, default=30, min=0, max=59),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Minutes to Close = session close se kitni minutes door. "
        "Last 15 mins flatten / no-new-trades policies ke liye."
    ),
    tags=["time", "intraday"],
    calculation_function="minutes_to_close",
)


_IS_EXPIRY_WEEK = IndicatorMetadata(
    id="is_expiry_week",
    name="Is Expiry Week (Monthly F&O)",
    category="Time",
    description=(
        "1.0 if the bar falls in the calendar week containing "
        "the last Thursday of the month (Indian F&O monthly "
        "expiry); 0.0 otherwise. Weekly-options expiry NOT "
        "covered (different weekday per symbol over time)."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Is Expiry Week = monthly F&O expiry week ke andar "
        "candle hai? Vol typically expiry week mein elevated, "
        "strategies adjust karte hain."
    ),
    tags=["time", "india", "expiry"],
    calculation_function="is_expiry_week",
)


# --- Session-aware (4) ----------------------------------------------


_SESSION_OPEN_DISTANCE = IndicatorMetadata(
    id="session_open_distance",
    name="Session Open Distance",
    category="Session",
    description=(
        "% distance between current close and the first bar's "
        "open of the trading day. Resets every session. None for "
        "daily-or-larger frequencies."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Session Open Distance = abhi ka close session open se "
        "kitne %. Strong morning move detection ke liye."
    ),
    tags=["session", "intraday"],
    calculation_function="session_open_distance",
)


_SESSION_HIGH_BREAKOUT = IndicatorMetadata(
    id="session_high_breakout",
    name="Session High Breakout",
    category="Session",
    description=(
        "1.0 when the bar prints a new running session high. "
        "0.0 otherwise. Resets every trading day."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Session High Breakout = bar ne session ka new high "
        "banaya. Intraday breakout signal."
    ),
    tags=["session", "breakout"],
    calculation_function="session_high_breakout",
)


_SESSION_LOW_BREAKOUT = IndicatorMetadata(
    id="session_low_breakout",
    name="Session Low Breakdown",
    category="Session",
    description=(
        "1.0 when the bar prints a new running session low. "
        "Mirror of session_high_breakout."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Session Low Breakdown = session ka new low ban gaya. "
        "Short / exit-long signal."
    ),
    tags=["session", "breakout"],
    calculation_function="session_low_breakout",
)


_SESSION_VOLUME_PACE = IndicatorMetadata(
    id="session_volume_pace",
    name="Session Volume Pace",
    category="Session",
    description=(
        "Today's cumulative volume divided by typical pace at "
        "this time-of-day, averaged over prior lookback_days "
        "trading sessions. > 1.0 = above pace; < 1.0 = below."
    ),
    inputs=[
        InputSpec(name="lookback_days", type=InputType.NUMBER, default=20, min=2, max=200),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Session Volume Pace = aaj ka cumulative volume vs "
        "typical pace at this time. >1.5 = heavy session "
        "(trends ki probability up), <0.7 = light (chop)."
    ),
    tags=["session", "volume"],
    calculation_function="session_volume_pace",
)


# --- Intraday-specific (4) ------------------------------------------


_FIRST_HOUR_RANGE = IndicatorMetadata(
    id="first_hour_range",
    name="First Hour Range",
    category="Session",
    description=(
        "high-low of the first ``minutes`` of each session "
        "(default 60). None during the opening window itself; "
        "constant for the rest of the day after."
    ),
    inputs=[
        InputSpec(name="minutes", type=InputType.NUMBER, default=60, min=5, max=240),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "First Hour Range = first 60 mins ka high-low. Large = "
        "trending session probable; tight = chop."
    ),
    tags=["session", "intraday"],
    calculation_function="first_hour_range",
)


_LAST_HOUR_MOMENTUM = IndicatorMetadata(
    id="last_hour_momentum",
    name="Last Hour Momentum",
    category="Session",
    description=(
        "% change between current close and the close of the bar "
        "that opened the last-hour window. None for bars before "
        "the window starts."
    ),
    inputs=[
        InputSpec(name="minutes", type=InputType.NUMBER, default=60, min=5, max=240),
        InputSpec(name="market_close_hour", type=InputType.NUMBER, default=15, min=0, max=23),
        InputSpec(name="market_close_min", type=InputType.NUMBER, default=30, min=0, max=59),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Last Hour Momentum = last 60 mins ka % change. "
        "Afternoon trend continuation ya exhaustion fade ke "
        "signals ke liye."
    ),
    tags=["session", "intraday", "momentum"],
    calculation_function="last_hour_momentum",
)


_LUNCH_CONSOLIDATION = IndicatorMetadata(
    id="lunch_consolidation",
    name="Lunch Consolidation",
    category="Session",
    description=(
        "1.0 when the bar is in lunch hours (default 12:00-"
        "13:00 IST) AND volume + range are below the running "
        "session averages. Chop-detection filter."
    ),
    inputs=[
        InputSpec(name="lunch_start_hour", type=InputType.NUMBER, default=12, min=0, max=22),
        InputSpec(name="lunch_end_hour", type=InputType.NUMBER, default=13, min=1, max=23),
    ],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.EXPERT,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Lunch Consolidation = quiet-hour detection (low vol + "
        "tight range). Chop period — most strategies stand "
        "down here."
    ),
    tags=["session", "intraday", "chop"],
    calculation_function="lunch_consolidation",
)


_OPENING_GAP_SIZE = IndicatorMetadata(
    id="opening_gap_size",
    name="Opening Gap Size",
    category="Session",
    description=(
        "% gap between today's open and yesterday's close. "
        "Continuous-% sibling of Pack 8's ``gap_up_down`` "
        "(which classifies)."
    ),
    inputs=[],
    outputs=["line"],
    chart_type=IndicatorChartType.SEPARATE,
    pine_aliases=[],
    difficulty=IndicatorDifficulty.INTERMEDIATE,
    status=IndicatorStatus.ACTIVE,
    ai_explanation=(
        "Opening Gap Size = aaj ke open vs kal ke close ka % "
        "gap. Continuous value (Pack 8 ka gap_up_down "
        "classifier alag concept)."
    ),
    tags=["session", "gap"],
    calculation_function="opening_gap_size",
)


# --- Aggregate -------------------------------------------------------


PACK15_ACTIVE_INDICATORS: tuple[IndicatorMetadata, ...] = (
    _DAY_OF_WEEK_SIGNAL,
    _HOUR_OF_DAY,
    _MINUTES_TO_CLOSE,
    _IS_EXPIRY_WEEK,
    _SESSION_OPEN_DISTANCE,
    _SESSION_HIGH_BREAKOUT,
    _SESSION_LOW_BREAKOUT,
    _SESSION_VOLUME_PACE,
    _FIRST_HOUR_RANGE,
    _LAST_HOUR_MOMENTUM,
    _LUNCH_CONSOLIDATION,
    _OPENING_GAP_SIZE,
)


__all__ = ["PACK15_ACTIVE_INDICATORS"]
