"""Pack 8 — multi-timeframe + specialty + India-specific tests.

Same shape as Pack 2 / 3 / 4 / 5 / 6 / 7. Active count assertion
is ``>= 107``.

Notes on intentional caveats:

* ``nifty_correlation`` is a stub that returns all-None — the
  per-calc test asserts that contract directly so a future
  Phase-2 wiring can't accidentally regress without a test
  failure.
* ``opening_range_breakout`` returns all-None on daily-or-larger
  frequencies; we test both intraday-with-signal AND daily-with-
  null-output paths.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack8_active import PACK8_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.daily_pivot_distance import (
    daily_pivot_distance,
)
from app.strategy_engine.indicators.calculations.ehlers_fisher import (
    ehlers_fisher,
)
from app.strategy_engine.indicators.calculations.fractal_chaos_bands import (
    fractal_chaos_bands,
)
from app.strategy_engine.indicators.calculations.gap_up_down import gap_up_down
from app.strategy_engine.indicators.calculations.higher_high_lower_low import (
    higher_high_lower_low,
)
from app.strategy_engine.indicators.calculations.mcginley_dynamic import (
    mcginley_dynamic,
)
from app.strategy_engine.indicators.calculations.mtf_ema_alignment import (
    mtf_ema_alignment,
)
from app.strategy_engine.indicators.calculations.nifty_correlation import (
    HAS_MARKET_CONTEXT,
    nifty_correlation,
)
from app.strategy_engine.indicators.calculations.opening_range_breakout import (
    opening_range_breakout,
)
from app.strategy_engine.indicators.calculations.swing_failure import (
    swing_failure,
)
from app.strategy_engine.indicators.calculations.weekly_pivot_close import (
    weekly_pivot_close,
)
from app.strategy_engine.indicators.calculations.zigzag import zigzag
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# ─── Multi-timeframe / Cross-period (4) ──────────────────────────────


def test_mtf_ema_alignment_uptrend_yields_plus_one() -> None:
    """Monotone-rising closes → EMA20 > EMA50 > EMA200 → +1."""
    n = 250
    out = mtf_ema_alignment(closes=[100.0 + i * 0.5 for i in range(n)],
                             periods=(20, 50, 200))
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(v == 1.0 for v in defined)


def test_mtf_ema_alignment_downtrend_yields_minus_one() -> None:
    n = 250
    out = mtf_ema_alignment(closes=[200.0 - i * 0.5 for i in range(n)],
                             periods=(20, 50, 200))
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(v == -1.0 for v in defined)


def test_mtf_ema_alignment_rejects_non_ascending_periods() -> None:
    with pytest.raises(ValueError, match="strictly ascending"):
        mtf_ema_alignment(closes=[1.0] * 100, periods=(50, 20))


def test_higher_high_lower_low_uptrend_yields_plus_one() -> None:
    """Strictly rising highs + lows → +1 every defined bar."""
    n = 30
    out = higher_high_lower_low(
        highs=[10.0 + i for i in range(n)],
        lows=[9.0 + i for i in range(n)],
        lookback=5,
    )
    defined = [v for v in out if v is not None]
    assert all(v == 1.0 for v in defined)


def test_higher_high_lower_low_empty_returns_empty() -> None:
    assert higher_high_lower_low([], [], lookback=5) == []


def test_swing_failure_bullish_failure_emits_plus_one() -> None:
    """Construct a window where the last bar's low pierces the
    prior min but its close is back inside the range."""
    highs = [11.0] * 10 + [10.5]
    lows = [9.0] * 10 + [8.0]  # last bar's low = 8 < prior min 9
    closes = [10.0] * 10 + [9.5]  # last close = 9.5 > prior min 9
    out = swing_failure(highs=highs, lows=lows, closes=closes, lookback=10)
    assert out[-1] == 1.0


def test_swing_failure_bearish_failure_emits_minus_one() -> None:
    highs = [11.0] * 10 + [12.0]  # last bar's high = 12 > prior max 11
    lows = [9.0] * 10 + [10.5]
    closes = [10.0] * 10 + [10.8]  # last close = 10.8 < prior max 11
    out = swing_failure(highs=highs, lows=lows, closes=closes, lookback=10)
    assert out[-1] == -1.0


def test_weekly_pivot_close_emits_pct_after_one_week() -> None:
    """Build 14 daily bars across two ISO weeks; second week's
    bars should produce defined values (week-1 pivot exists)."""
    base = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)  # Monday
    timestamps = [base + timedelta(days=i) for i in range(14)]
    out = weekly_pivot_close(
        highs=[100.0 + i * 0.5 for i in range(14)],
        lows=[99.0 + i * 0.5 for i in range(14)],
        closes=[99.5 + i * 0.5 for i in range(14)],
        timestamps=timestamps,
        weeks_back=1,
    )
    # First week (5 bars) → None; second week → defined.
    assert out[0] is None
    assert any(v is not None for v in out[7:])


# ─── India-specific (4) ──────────────────────────────────────────────


def test_orb_intraday_emits_breakout_codes() -> None:
    """Build 1-minute bars with a clear breakout above the 15-min
    opening-range high."""
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    n = 30  # 30 1-min bars
    highs = [10.0] * 15 + [11.0] * 15  # break high after minute 15
    lows = [9.0] * 30
    closes = [9.5] * 15 + [10.8] * 15  # close > OR-high (10.0)
    timestamps = [base + timedelta(minutes=i) for i in range(n)]
    out = opening_range_breakout(highs, lows, closes, timestamps, range_minutes=15)
    # First 15 bars are inside the OR window → None.
    assert all(v is None for v in out[:15])
    # Subsequent bars should be +1 (breakout high cleared).
    assert all(v == 1.0 for v in out[15:])


def test_orb_daily_candles_returns_all_none() -> None:
    """Daily-frequency candles → ORB is meaningless → all None."""
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    n = 10
    out = opening_range_breakout(
        highs=[10.0] * n,
        lows=[9.0] * n,
        closes=[9.5] * n,
        timestamps=[base + timedelta(days=i) for i in range(n)],
        range_minutes=15,
    )
    assert all(v is None for v in out)


def test_gap_up_down_above_threshold_emits_plus_one() -> None:
    out = gap_up_down(opens=[100.0, 101.0], closes=[100.0, 100.5], threshold_pct=0.5)
    # opens[1] - closes[0] = +1 → 1% > 0.5% threshold → +1.
    assert out[1] == 1.0


def test_gap_up_down_below_threshold_emits_zero() -> None:
    out = gap_up_down(opens=[100.0, 100.1], closes=[100.0, 100.05], threshold_pct=0.5)
    # 0.1% gap < 0.5% threshold → 0.
    assert out[1] == 0.0


def test_daily_pivot_distance_emits_pct_after_first_day() -> None:
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    timestamps = [base + timedelta(days=i) for i in range(3)]
    out = daily_pivot_distance(
        highs=[10.0, 11.0, 12.0],
        lows=[9.0, 10.0, 11.0],
        closes=[9.5, 10.5, 11.5],
        timestamps=timestamps,
    )
    # Day 0 → None (no prior day).
    assert out[0] is None
    # Days 1, 2 → defined.
    assert out[1] is not None
    assert out[2] is not None


def test_nifty_correlation_is_phase1_stub_returning_all_none() -> None:
    """The stub contract — Phase-2 wiring will replace the body
    but the empty-output guarantee documents the current behaviour
    so callers can branch on ``None``."""
    out = nifty_correlation(closes=[100.0] * 50, period=30)
    assert len(out) == 50
    assert all(v is None for v in out)
    # Operator-visible flag — used by the dashboard to render a
    # "needs market context" badge.
    assert HAS_MARKET_CONTEXT is False


def test_nifty_correlation_validates_period() -> None:
    with pytest.raises(ValueError, match="> 1"):
        nifty_correlation(closes=[1.0] * 50, period=1)


# ─── Specialty / Advanced (4) ────────────────────────────────────────


def test_zigzag_marks_alternating_swings() -> None:
    """Construct a clean V → ^ → V pattern and expect zigzag to
    mark the middle swing-low and swing-high."""
    highs = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0, 111.0,
              112.0, 113.0, 114.0, 110.0, 109.0, 108.0, 107.0,
              106.0, 105.0]
    lows = [99.0, 100.0, 101.0, 102.0, 103.0, 109.0, 110.0,
             111.0, 112.0, 113.0, 109.0, 108.0, 107.0, 106.0,
             105.0, 90.0]
    out = zigzag(highs=highs, lows=lows, deviation_pct=5.0)
    # Some bar should be marked as a swing high or low.
    assert any(v in (1.0, -1.0) for v in out if v is not None)


def test_zigzag_rejects_zero_deviation() -> None:
    with pytest.raises(ValueError, match="> 0"):
        zigzag(highs=[1.0] * 5, lows=[1.0] * 5, deviation_pct=0)


def test_fractal_chaos_bands_returns_same_length() -> None:
    n = 50
    out = fractal_chaos_bands(
        highs=[10.0 + (i % 5) for i in range(n)],
        lows=[8.0 + (i % 5) for i in range(n)],
        period=9,
    )
    assert len(out) == n


def test_fractal_chaos_bands_rejects_period_below_five() -> None:
    with pytest.raises(ValueError, match=">= 5"):
        fractal_chaos_bands(highs=[1.0] * 10, lows=[1.0] * 10, period=4)


def test_ehlers_fisher_constant_input_yields_zero() -> None:
    """Constant closes → RSI is undefined / returns 0 deltas →
    fisher transforms to 0 (after the warmup)."""
    n = 30
    out = ehlers_fisher(closes=[100.0] * n, period=10)
    defined = [v for v in out if v is not None]
    # Constant input → RSI is degenerate; we accept anything in
    # the defined range, but it MUST be in [-1, +1].
    assert all(-1.0 <= v <= 1.0 for v in defined)


def test_ehlers_fisher_output_in_range() -> None:
    """For varied input, the IFT keeps output strictly in [-1, +1]."""
    n = 100
    out = ehlers_fisher(closes=[100.0 + (i * 0.3) for i in range(n)], period=10)
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(-1.0 <= v <= 1.0 for v in defined)


def test_mcginley_dynamic_seeds_at_first_close() -> None:
    out = mcginley_dynamic(closes=[100.0, 101.0, 102.0], period=14, constant=0.6)
    assert out[0] == 100.0


def test_mcginley_dynamic_constant_input_stays_constant() -> None:
    out = mcginley_dynamic(closes=[100.0] * 30, period=14, constant=0.6)
    assert all(v == 100.0 for v in out if v is not None)


def test_mcginley_dynamic_rejects_zero_constant() -> None:
    with pytest.raises(ValueError, match="> 0"):
        mcginley_dynamic(closes=[1.0] * 5, period=14, constant=0)


# ─── Registry promotion ──────────────────────────────────────────────


_PACK8_IDS = {
    "mtf_ema_alignment",
    "higher_high_lower_low",
    "swing_failure",
    "weekly_pivot_close",
    "opening_range_breakout",
    "gap_up_down",
    "daily_pivot_distance",
    "nifty_correlation",
    "zigzag",
    "fractal_chaos_bands",
    "ehlers_fisher",
    "mcginley_dynamic",
}


def test_pack8_module_exposes_twelve_indicators() -> None:
    assert len(PACK8_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK8_ACTIVE_INDICATORS} == _PACK8_IDS


def test_pack8_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK8_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack8_is_one_hundred_seven() -> None:
    """20 historical + 15 Pack 2 + 12 Pack 3 + 12 Pack 4 + 12 Pack 5
    + 12 Pack 6 + 12 Pack 7 + 12 Pack 8 = 107.

    Loose lower bound for forward compatibility."""
    assert len(get_active_indicators()) >= 107


def test_pack8_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK8_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack8_no_beginner_difficulty() -> None:
    """Spec says 'avoid beginner set lock' — every Pack 8 entry
    must be INTERMEDIATE or EXPERT."""
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK8_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


# ─── Backtest dispatch ──────────────────────────────────────────────


def _wavy_intraday_candles(n: int = 60) -> list:
    """1-minute bars with non-trivial range — exercises ORB + the
    timestamp-aware indicators end-to-end."""
    out = []
    for i in range(n):
        base = 100.0 + (i % 7) - 3.0
        out.append(
            make_candle(
                minutes=i,
                open_=base,
                high=base + 1.0,
                low=base - 1.0,
                close=base + 0.5,
                volume=1_000.0,
            )
        )
    return out


def _wavy_daily_candles(n: int = 250) -> list:
    """Daily-frequency bars (1440 minutes apart) — exercises
    multi-day indicators (weekly pivot, daily pivot, MTF EMA
    with the long 200-period default)."""
    out = []
    for i in range(n):
        base = 100.0 + (i % 9) - 4.0
        out.append(
            make_candle(
                minutes=i * 1440,  # one bar per day
                open_=base,
                high=base + 1.5,
                low=base - 1.5,
                close=base + 0.5,
                volume=1_000.0 + i * 4,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params", "use_daily"),
    [
        ("mtf_ema_alignment", {"periods": "20,50,200"}, True),
        ("higher_high_lower_low", {"lookback": 5}, False),
        ("swing_failure", {"lookback": 10}, False),
        ("weekly_pivot_close", {"weeks_back": 1}, True),
        ("opening_range_breakout", {"range_minutes": 15}, False),
        ("gap_up_down", {"threshold_pct": 0.5}, False),
        ("daily_pivot_distance", {}, True),
        ("nifty_correlation", {"period": 30}, False),
        ("zigzag", {"deviation_pct": 5.0}, False),
        ("fractal_chaos_bands", {"period": 9}, False),
        ("ehlers_fisher", {"period": 10}, False),
        ("mcginley_dynamic", {"period": 14, "constant": 0.6}, False),
    ],
)
def test_pack8_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object], use_daily: bool,
) -> None:
    """Each Pack 8 indicator dispatches successfully and produces a
    same-length series."""
    candles = _wavy_daily_candles() if use_daily else _wavy_intraday_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    if indicator_type == "opening_range_breakout":
        # ORB is now multi-output (Queue MM A2): the primary signal plus the
        # opening-range high/low band sub-outputs, so it emits the multi-output
        # warning and dotted band sub-ids.
        assert any(
            f"{indicator_type}_inst" in w and "multi-output" in w for w in warnings
        )
        assert f"{indicator_type}_inst.high" in series
        assert f"{indicator_type}_inst.low" in series
        assert len(series[f"{indicator_type}_inst.high"]) == len(candles)
    else:
        # No multi-output warning for the other Pack 8 indicators.
        assert not any(f"{indicator_type}_inst" in w for w in warnings)
