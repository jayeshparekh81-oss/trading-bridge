"""Pack 16 - options-aware + Greeks-PROXY tests.

Same shape as Pack 2-15. Active count assertion ``>= 203``.

Greek tests assert *qualitative* / proxy behavior - we're NOT
claiming Black-Scholes correctness. The vix_correlation stub
gets explicit contract assertion. No new Pine wiring; pinned
by the Pack 16 lock test.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack16_active import (
    PACK16_ACTIVE_INDICATORS,
)
from app.strategy_engine.indicators.calculations.atm_strike_distance import (
    atm_strike_distance,
)
from app.strategy_engine.indicators.calculations.delta_proxy_directional import (
    delta_proxy_directional,
)
from app.strategy_engine.indicators.calculations.expiry_day_volatility import (
    expiry_day_volatility,
)
from app.strategy_engine.indicators.calculations.gamma_proxy_acceleration import (
    gamma_proxy_acceleration,
)
from app.strategy_engine.indicators.calculations.iv_percentile import (
    iv_percentile,
)
from app.strategy_engine.indicators.calculations.iv_proxy_atr import iv_proxy_atr
from app.strategy_engine.indicators.calculations.iv_rank import iv_rank
from app.strategy_engine.indicators.calculations.monthly_pivot_distance import (
    monthly_pivot_distance,
)
from app.strategy_engine.indicators.calculations.round_number_attraction import (
    round_number_attraction,
)
from app.strategy_engine.indicators.calculations.theta_proxy_decay import (
    theta_proxy_decay,
)
from app.strategy_engine.indicators.calculations.vega_proxy_iv_sensitivity import (
    vega_proxy_iv_sensitivity,
)
from app.strategy_engine.indicators.calculations.vix_correlation import (
    HAS_VIX_CONTEXT,
    vix_correlation,
)
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

# --- IV Proxies (4) -------------------------------------------------


def test_iv_proxy_atr_constant_input_yields_zero() -> None:
    """Flat highs == lows -> ATR = 0 -> annualised value = 0."""
    out = iv_proxy_atr(
        highs=[100.0] * 30, lows=[100.0] * 30, closes=[100.0] * 30,
        atr_period=20, bars_per_year=252,
    )
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_iv_proxy_atr_returns_in_annualised_scale() -> None:
    """For a constant 1% range, the annualised value should be larger
    than the un-annualised ATR percent (factor sqrt(252) ~= 15.87)."""
    n = 30
    out = iv_proxy_atr(
        highs=[101.0] * n, lows=[100.0] * n, closes=[100.5] * n,
        atr_period=20, bars_per_year=252,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    # ATR%/100 of ~1, annualised by sqrt(252) ~= 15.87.
    assert all(v == pytest.approx(15.87, abs=0.5) for v in defined)


def test_iv_rank_flat_window_returns_fifty() -> None:
    """When max == min in the lookback window, IV Rank conventionally
    returns 50 (midpoint)."""
    n = 280
    out = iv_rank(
        highs=[101.0] * n, lows=[100.0] * n, closes=[100.5] * n,
        lookback=252, atr_period=20,
    )
    defined = [v for v in out if v is not None]
    assert all(v == pytest.approx(50.0) for v in defined)


def test_iv_percentile_returns_in_zero_to_hundred() -> None:
    """For varied data, percentile output should land in [0, 100]."""
    import math as _math
    n = 300
    out = iv_percentile(
        highs=[101.0 + _math.sin(i * 0.1) for i in range(n)],
        lows=[100.0 + _math.sin(i * 0.1) for i in range(n)],
        closes=[100.5 + _math.sin(i * 0.1) for i in range(n)],
        lookback=252, atr_period=20,
    )
    defined = [v for v in out if v is not None]
    assert all(0.0 <= v <= 100.0 for v in defined)


def test_vix_correlation_is_phase1_stub() -> None:
    """Stub contract: returns all-None for any input length."""
    out = vix_correlation(closes=[100.0] * 50, period=30)
    assert len(out) == 50
    assert all(v is None for v in out)


def test_vix_correlation_flag() -> None:
    assert HAS_VIX_CONTEXT is False


def test_vix_correlation_rejects_low_period() -> None:
    with pytest.raises(ValueError, match="> 1"):
        vix_correlation(closes=[1.0] * 50, period=1)


# --- Options Activity (4) -------------------------------------------


def test_atm_strike_distance_at_strike_yields_zero() -> None:
    """Close exactly at a strike grid point -> distance = 0."""
    out = atm_strike_distance(closes=[24500.0], strike_step=100.0)
    assert out[0] == pytest.approx(0.0)


def test_atm_strike_distance_off_strike_yields_pct() -> None:
    """Close 24550 with strike_step 100 -> nearest strike 24600
    (round half away from zero is 24500 in Python — but
    Python's round() uses banker's rounding: 24550 / 100 = 245.5
    -> rounds to 246 -> nearest = 24600). Test the actual behavior."""
    out = atm_strike_distance(closes=[24530.0], strike_step=100.0)
    # 24530 / 100 = 245.3 -> rounds to 245 -> nearest = 24500.
    # Distance = (24530 - 24500) / 24500 * 100 = 0.122%.
    assert out[0] == pytest.approx(0.122, abs=0.01)


def test_atm_strike_distance_rejects_zero_step() -> None:
    with pytest.raises(ValueError, match="> 0"):
        atm_strike_distance(closes=[100.0], strike_step=0)


def test_round_number_attraction_close_to_strike_yields_one() -> None:
    """Close at exactly the strike -> 1.0."""
    out = round_number_attraction(
        closes=[24500.0], strike_step=100.0, threshold_pct=0.5,
    )
    assert out[0] == 1.0


def test_round_number_attraction_far_from_strike_yields_zero() -> None:
    """Close 24545 from strike 24500 -> 0.18% < 0.5% -> still 1.0.
    But close 24560 from strike 24500 -> 0.245% < 0.5% -> 1.0.
    Use a clearly-far value: close 24535 from strike 24500 ->
    0.143% < 0.5% -> still 1. Need a close like 24420 vs 24400 ->
    0.5% exactly. Anything closer to mid-strike (24450) is far."""
    # 24450 from nearest strike: 24500 - 24450 = 50 -> 0.20%. Still
    # within 0.5%. Use a wider threshold or closer-to-mid value:
    out = round_number_attraction(
        closes=[24460.0], strike_step=100.0, threshold_pct=0.05,
    )
    # 24460 vs strike 24500: 40/24500 = 0.163% > 0.05% -> 0.
    assert out[0] == 0.0


def test_expiry_day_volatility_no_history_returns_none() -> None:
    """First Thursday in the input has no prior Thursdays."""
    base = datetime(2026, 5, 7, 9, 15, tzinfo=UTC)  # Thursday
    timestamps = [base + timedelta(minutes=i * 5) for i in range(20)]
    out = expiry_day_volatility(
        highs=[101.0] * 20, lows=[100.0] * 20, timestamps=timestamps,
        weekday_target=3, history_sessions=4,
    )
    assert all(v is None for v in out)


def test_expiry_day_volatility_daily_returns_all_none() -> None:
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    timestamps = [base + timedelta(days=i) for i in range(10)]
    out = expiry_day_volatility(
        highs=[101.0] * 10, lows=[100.0] * 10, timestamps=timestamps,
    )
    assert all(v is None for v in out)


def test_monthly_pivot_distance_no_prior_month_returns_none() -> None:
    """All bars in same month -> no prior-month pivot -> all None."""
    base = datetime(2026, 5, 4, 9, 15, tzinfo=UTC)
    timestamps = [base + timedelta(days=i) for i in range(15)]
    out = monthly_pivot_distance(
        highs=[101.0] * 15, lows=[99.0] * 15, closes=[100.0] * 15,
        timestamps=timestamps, months_back=1,
    )
    assert all(v is None for v in out)


def test_monthly_pivot_distance_emits_pct_after_month_change() -> None:
    """Build bars across 2 months; second month should get values."""
    timestamps = []
    base_april = datetime(2026, 4, 1, 9, 15, tzinfo=UTC)
    base_may = datetime(2026, 5, 1, 9, 15, tzinfo=UTC)
    for i in range(20):
        timestamps.append(base_april + timedelta(days=i))
    for i in range(15):
        timestamps.append(base_may + timedelta(days=i))
    n = len(timestamps)
    out = monthly_pivot_distance(
        highs=[101.0] * n, lows=[99.0] * n, closes=[100.0] * n,
        timestamps=timestamps, months_back=1,
    )
    # April bars -> None (no prior). May bars -> defined.
    assert all(v is None for v in out[:20])
    assert any(v is not None for v in out[20:])


# --- Greeks Proxies (4) ---------------------------------------------


def test_delta_proxy_returns_in_unit_range() -> None:
    """Bounded output [-1, +1]."""
    n = 100
    out = delta_proxy_directional(
        highs=[101.0 + (i % 3) for i in range(n)],
        lows=[99.0 + (i % 3) for i in range(n)],
        closes=[100.0 + (i % 3) for i in range(n)],
        period=14,
    )
    defined = [v for v in out if v is not None]
    assert all(-1.0 <= v <= 1.0 for v in defined)


def test_delta_proxy_strong_uptrend_yields_positive() -> None:
    """Strict monotone uptrend -> close above SMA -> positive bias."""
    n = 30
    out = delta_proxy_directional(
        highs=[101.0 + i for i in range(n)],
        lows=[99.0 + i for i in range(n)],
        closes=[100.0 + i for i in range(n)],
        period=14,
    )
    last = out[-1]
    assert last is not None
    assert last > 0.0


def test_theta_proxy_returns_finite_on_synthetic() -> None:
    n = 50
    out = theta_proxy_decay(
        highs=[101.0 + (i % 3) for i in range(n)],
        lows=[99.0 + (i % 3) for i in range(n)],
        lookback=20,
    )
    defined = [v for v in out if v is not None]
    assert len(defined) > 0
    assert all(math.isfinite(v) for v in defined)


def test_theta_proxy_rejects_short_lookback() -> None:
    with pytest.raises(ValueError, match=">= 4"):
        theta_proxy_decay(highs=[1.0] * 30, lows=[1.0] * 30, lookback=3)


def test_vega_proxy_rejects_short_geq_long() -> None:
    with pytest.raises(ValueError, match="strictly less"):
        vega_proxy_iv_sensitivity(
            highs=[1.0] * 50, lows=[1.0] * 50, closes=[1.0] * 50,
            short=20, long=20,
        )


def test_vega_proxy_returns_same_length() -> None:
    n = 100
    out = vega_proxy_iv_sensitivity(
        highs=[101.0 + math.sin(i * 0.2) for i in range(n)],
        lows=[99.0 + math.sin(i * 0.2) for i in range(n)],
        closes=[100.0 + math.sin(i * 0.2) for i in range(n)],
        short=5, long=20,
    )
    assert len(out) == n


def test_gamma_proxy_constant_input_yields_zero() -> None:
    """Constant closes -> velocity = 0 -> acceleration = 0."""
    out = gamma_proxy_acceleration(closes=[100.0] * 30, period=10)
    defined = [v for v in out if v is not None]
    assert all(v == 0.0 for v in defined)


def test_gamma_proxy_accelerating_uptrend_positive() -> None:
    """y = i**2 -> velocity = 2i + 1 -> acceleration = 2 (constant +).
    Smoothed average should be ~2."""
    n = 50
    out = gamma_proxy_acceleration(
        closes=[float(i * i) for i in range(n)], period=10,
    )
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(2.0, abs=0.5)


# --- Registry promotion ---------------------------------------------


_PACK16_IDS = {
    "iv_proxy_atr",
    "iv_rank",
    "iv_percentile",
    "vix_correlation",
    "atm_strike_distance",
    "round_number_attraction",
    "expiry_day_volatility",
    "monthly_pivot_distance",
    "delta_proxy_directional",
    "theta_proxy_decay",
    "vega_proxy_iv_sensitivity",
    "gamma_proxy_acceleration",
}


def test_pack16_module_exposes_twelve_indicators() -> None:
    assert len(PACK16_ACTIVE_INDICATORS) == 12
    assert {meta.id for meta in PACK16_ACTIVE_INDICATORS} == _PACK16_IDS


def test_pack16_indicators_are_active_in_registry() -> None:
    for ind_id in _PACK16_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE
        assert meta.calculation_function == ind_id


def test_active_count_after_pack16_is_two_hundred_three() -> None:
    """Pack-15 baseline 191 + 12 Pack 16 = 203."""
    assert len(get_active_indicators()) >= 203


def test_pack16_calculation_functions_are_resolvable() -> None:
    for ind_id in _PACK16_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"


def test_pack16_no_beginner_difficulty() -> None:
    from app.strategy_engine.schema.indicator import IndicatorDifficulty

    for meta in PACK16_ACTIVE_INDICATORS:
        assert meta.difficulty in (
            IndicatorDifficulty.INTERMEDIATE,
            IndicatorDifficulty.EXPERT,
        ), f"{meta.id} has difficulty {meta.difficulty}; expected INTERMEDIATE/EXPERT"


def test_pack16_has_no_pine_aliases() -> None:
    for meta in PACK16_ACTIVE_INDICATORS:
        assert meta.pine_aliases == [], (
            f"{meta.id} unexpectedly has Pine aliases: {meta.pine_aliases}"
        )


def test_pack16_greeks_proxies_documented_in_descriptions() -> None:
    """Lock test: every Greek-named indicator must say PROXY in
    its description so users can't mistake them for real Greeks."""
    greek_ids = (
        "delta_proxy_directional", "theta_proxy_decay",
        "vega_proxy_iv_sensitivity", "gamma_proxy_acceleration",
    )
    for ind_id in greek_ids:
        meta = INDICATOR_REGISTRY[ind_id]
        assert "PROXY" in meta.description.upper(), (
            f"{ind_id} description must say PROXY (got: {meta.description!r})"
        )


# --- Backtest dispatch ----------------------------------------------


def _wavy_intraday_candles(n: int = 300) -> list:
    """Synthetic intraday candles - large enough for IV-rank's
    default 252 lookback + the iv_proxy_atr 20-bar warmup."""
    out = []
    for i in range(n):
        base = 24500.0 + math.sin(i * 0.1) * 50.0 + (i % 5) * 2
        out.append(
            make_candle(
                minutes=i * 5,  # 5-minute bars
                open_=base,
                high=base + 30,
                low=base - 30,
                close=base + 10,
                volume=1_000.0 + i,
            )
        )
    return out


@pytest.mark.parametrize(
    ("indicator_type", "params"),
    [
        ("iv_proxy_atr", {"atr_period": 20, "bars_per_year": 252}),
        ("iv_rank", {"lookback": 252, "atr_period": 20}),
        ("iv_percentile", {"lookback": 252, "atr_period": 20}),
        ("vix_correlation", {"period": 30}),
        ("atm_strike_distance", {"strike_step": 100.0}),
        (
            "round_number_attraction",
            {"strike_step": 100.0, "threshold_pct": 0.5},
        ),
        (
            "expiry_day_volatility",
            {"weekday_target": 3, "history_sessions": 4},
        ),
        ("monthly_pivot_distance", {"months_back": 1}),
        ("delta_proxy_directional", {"period": 14}),
        ("theta_proxy_decay", {"lookback": 20}),
        ("vega_proxy_iv_sensitivity", {"short": 5, "long": 20}),
        ("gamma_proxy_acceleration", {"period": 10}),
    ],
)
def test_pack16_dispatch_produces_populated_series(
    indicator_type: str, params: dict[str, object]
) -> None:
    """Each Pack 16 indicator dispatches successfully and produces
    a same-length series."""
    candles = _wavy_intraday_candles()
    strategy = make_strategy(
        indicators=[
            {"id": f"{indicator_type}_inst", "type": indicator_type, "params": params}
        ],
    )
    series, warnings = precompute_indicators(candles, strategy)
    primary = series[f"{indicator_type}_inst"]
    assert len(primary) == len(candles)
    assert not any(f"{indicator_type}_inst" in w for w in warnings)
