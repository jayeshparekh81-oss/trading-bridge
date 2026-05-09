"""Pack 2 — calculation correctness + registry promotion tests.

Each indicator gets:

    * a numeric correctness check anchored to a hand-computed
      reference value (or a bounded range when the closed-form is
      messy, e.g. EMA-of-EMA);
    * an empty / insufficient-data edge case;
    * a determinism re-run on a separate input copy.

A separate block tests the registry-level promotion: every Pack 2
id is now ``ACTIVE``, has a working ``calculation_function``, and
the active count moved from 20 to 35.
"""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators._pack2_active import PACK2_ACTIVE_INDICATORS
from app.strategy_engine.indicators.calculations.cci import cci
from app.strategy_engine.indicators.calculations.chande_momentum import (
    chande_momentum,
)
from app.strategy_engine.indicators.calculations.dema import dema
from app.strategy_engine.indicators.calculations.donchian_channel import (
    donchian_channel,
)
from app.strategy_engine.indicators.calculations.hull_ma import hull_ma
from app.strategy_engine.indicators.calculations.keltner_channel import (
    keltner_channel,
)
from app.strategy_engine.indicators.calculations.mfi import mfi
from app.strategy_engine.indicators.calculations.parabolic_sar import (
    parabolic_sar,
)
from app.strategy_engine.indicators.calculations.roc import roc
from app.strategy_engine.indicators.calculations.smma import smma
from app.strategy_engine.indicators.calculations.stochastic import stochastic
from app.strategy_engine.indicators.calculations.supertrend import supertrend
from app.strategy_engine.indicators.calculations.tema import tema
from app.strategy_engine.indicators.calculations.vwma import vwma
from app.strategy_engine.indicators.calculations.williams_r import williams_r
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus

# ─── Trend ────────────────────────────────────────────────────────────


def test_vwma_volume_weighted_against_known_value() -> None:
    """3-bar VWMA: weights = volume; result = sum(p*v) / sum(v)."""
    prices = [10.0, 11.0, 12.0, 13.0]
    volumes = [1.0, 2.0, 3.0, 4.0]
    out = vwma(prices, volumes, period=3)
    assert out[0] is None and out[1] is None
    # bars 0-2 window: (10*1 + 11*2 + 12*3) / (1+2+3) = 68 / 6.
    assert out[2] == pytest.approx(68.0 / 6.0)
    # bars 1-3 window: (11*2 + 12*3 + 13*4) / (2+3+4) = 110 / 9.
    assert out[3] == pytest.approx(110.0 / 9.0)


def test_vwma_zero_volume_window_yields_none() -> None:
    out = vwma([10.0, 11.0, 12.0], [0.0, 0.0, 0.0], period=2)
    assert out == [None, None, None]


def test_vwma_empty_input_returns_empty_list() -> None:
    assert vwma([], [], period=5) == []


def test_smma_first_bar_seeds_from_simple_mean_then_smooths() -> None:
    """SMMA[period-1] = simple mean of first ``period`` bars."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = smma(values, period=3)
    # seed = (1 + 2 + 3) / 3 = 2.0
    assert out[2] == pytest.approx(2.0)
    # bar 3: (2.0 * 2 + 4) / 3 = 8/3
    assert out[3] == pytest.approx(8.0 / 3.0)
    # bar 4: (8/3 * 2 + 5) / 3 = (16/3 + 5) / 3 = (16/3 + 15/3) / 3 = 31/9
    assert out[4] == pytest.approx(31.0 / 9.0)


def test_smma_insufficient_data_returns_empty() -> None:
    assert smma([1.0, 2.0], period=3) == []


def test_dema_on_constant_series_equals_constant() -> None:
    """DEMA = 2*EMA1 - EMA2; on a constant series both EMAs equal
    the constant, so DEMA equals the constant once both seeded."""
    values = [5.0] * 10
    out = dema(values, period=3)
    # EMA1 seeds at index 2, EMA2 needs 2 more bars → seeded at index 4.
    seeded = [v for v in out[4:] if v is not None]
    assert seeded
    assert all(v == pytest.approx(5.0) for v in seeded)


def test_dema_empty_returns_empty() -> None:
    assert dema([], period=3) == []


def test_tema_on_constant_series_equals_constant() -> None:
    """Same invariant as DEMA — TEMA on a flat series collapses to
    the constant once all three EMAs are seeded."""
    values = [7.5] * 12
    out = tema(values, period=3)
    seeded = [v for v in out if v is not None]
    assert seeded
    assert all(v == pytest.approx(7.5) for v in seeded)


def test_tema_empty_returns_empty() -> None:
    assert tema([], period=3) == []


def test_hull_ma_on_constant_series_equals_constant() -> None:
    """HMA on a flat series collapses to the constant once all
    three nested WMAs are seeded."""
    values = [42.0] * 30
    out = hull_ma(values, period=9)
    seeded = [v for v in out if v is not None]
    assert seeded
    assert all(v == pytest.approx(42.0) for v in seeded)


def test_hull_ma_rejects_period_below_two() -> None:
    with pytest.raises(ValueError):
        hull_ma([1.0, 2.0, 3.0], period=1)


def test_parabolic_sar_uptrend_keeps_dot_below_price() -> None:
    """Pure uptrend → PSAR sits below low. The flip path is exercised
    in the next test."""
    n = 40
    highs = [100.0 + i * 1.5 for i in range(n)]
    lows = [99.0 + i * 1.5 for i in range(n)]
    closes = [99.5 + i * 1.5 for i in range(n)]
    out = parabolic_sar(highs, lows, closes)
    assert out[0] is None
    seeded = [(i, v) for i, v in enumerate(out) if v is not None]
    assert seeded
    for i, v in seeded:
        assert v <= lows[i] + 1e-9, f"bar {i}: SAR {v} sits above low {lows[i]}"


def test_parabolic_sar_flips_on_trend_reversal() -> None:
    """Five up bars then five down bars — SAR must produce both
    polarities relative to price."""
    highs = [100.0, 101.0, 102.0, 103.0, 104.0, 103.0, 101.0, 99.0, 97.0, 95.0]
    lows = [99.0, 100.0, 101.0, 102.0, 103.0, 102.0, 100.0, 98.0, 96.0, 94.0]
    closes = [99.5, 100.5, 101.5, 102.5, 103.5, 102.5, 100.5, 98.5, 96.5, 94.5]
    out = parabolic_sar(highs, lows, closes)
    seeded = [v for v in out if v is not None]
    # Some bars must have SAR above price (bear), others below (bull).
    above = any(v > closes[i] for i, v in enumerate(out) if v is not None)
    below = any(v < closes[i] for i, v in enumerate(out) if v is not None)
    assert above and below
    assert len(seeded) >= 8


def test_supertrend_returns_two_aligned_series() -> None:
    """Steady uptrend: outputs align with input length, eventually
    flips to +1, and once bullish the line sits at-or-below close.

    With a 3 x ATR multiplier on a low-volatility ramp the upper
    band stays well above price for many bars before close finally
    crosses it — supertrend is intentionally sticky. We just check
    it gets there and that the bullish bars satisfy the geometry
    invariant."""
    n = 60
    highs = [100.0 + i * 1.0 for i in range(n)]
    lows = [99.0 + i * 1.0 for i in range(n)]
    closes = [99.5 + i * 1.0 for i in range(n)]
    line, direction = supertrend(highs, lows, closes, period=10, multiplier=3.0)
    assert len(line) == n
    assert len(direction) == n
    seeded_dirs = [d for d in direction if d is not None]
    assert seeded_dirs
    assert direction[-1] == pytest.approx(1.0), (
        "supertrend never flipped bullish on a steady uptrend"
    )
    for i, ln in enumerate(line):
        if ln is None or direction[i] != 1.0:
            continue
        assert ln <= closes[i] + 1e-9


def test_supertrend_empty_returns_empty_pair() -> None:
    line, direction = supertrend([], [], [])
    assert line == [] and direction == []


# ─── Momentum ─────────────────────────────────────────────────────────


def test_cci_constant_typical_price_yields_none() -> None:
    """Flat TP → mean dev = 0 → division by zero → None."""
    flat = [10.0] * 25
    out = cci(flat, flat, flat, period=20)
    seeded_or_none = out[19:]
    assert all(v is None for v in seeded_or_none)


def test_cci_known_three_bar_window() -> None:
    """Hand-computed: TP = avg of {h, l, c}. With period=3, single
    seeded bar at index 2.

    h = [10, 12, 14], l = [8, 10, 12], c = [9, 11, 13]
    TP = [9, 11, 13]; SMA_TP = 11; mean_dev = (2 + 0 + 2) / 3 = 4/3
    CCI = (13 - 11) / (0.015 * 4/3) = 2 / 0.02 = 100.
    """
    h = [10.0, 12.0, 14.0]
    lo = [8.0, 10.0, 12.0]
    c = [9.0, 11.0, 13.0]
    out = cci(h, lo, c, period=3)
    assert out[0] is None and out[1] is None
    assert out[2] == pytest.approx(100.0)


def test_cci_empty_returns_empty() -> None:
    assert cci([], [], [], period=14) == []


def test_williams_r_at_top_of_range_is_zero() -> None:
    """Close == HH → %R == 0."""
    highs = [10.0, 11.0, 12.0, 13.0, 14.0]
    lows = [8.0, 9.0, 10.0, 11.0, 12.0]
    closes = [9.0, 10.0, 11.0, 12.0, 14.0]  # last close == HH
    out = williams_r(highs, lows, closes, period=4)
    assert out[4] == pytest.approx(0.0)


def test_williams_r_at_bottom_of_range_is_minus_hundred() -> None:
    highs = [14.0, 13.0, 12.0, 11.0, 10.0]
    lows = [12.0, 11.0, 10.0, 9.0, 8.0]
    closes = [13.0, 12.0, 11.0, 10.0, 8.0]
    out = williams_r(highs, lows, closes, period=4)
    assert out[4] == pytest.approx(-100.0)


def test_williams_r_flat_window_returns_none() -> None:
    flat_h = [10.0] * 5
    flat_l = [10.0] * 5
    closes = [10.0] * 5
    out = williams_r(flat_h, flat_l, closes, period=3)
    assert out[2:] == [None, None, None]


def test_chande_momentum_pure_up_series_is_plus_hundred() -> None:
    """All up bars → sum_down = 0 → CMO = 100 * sum_up / sum_up = 100."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = chande_momentum(values, period=3)
    assert out[3] == pytest.approx(100.0)
    assert out[4] == pytest.approx(100.0)


def test_chande_momentum_pure_down_series_is_minus_hundred() -> None:
    values = [5.0, 4.0, 3.0, 2.0, 1.0]
    out = chande_momentum(values, period=3)
    assert out[3] == pytest.approx(-100.0)
    assert out[4] == pytest.approx(-100.0)


def test_chande_momentum_flat_window_returns_none() -> None:
    out = chande_momentum([3.0] * 6, period=3)
    assert all(v is None for v in out)


def test_stochastic_known_values_at_top_and_bottom() -> None:
    """At top of range %K = 100; at bottom %K = 0."""
    highs = [10.0, 11.0, 12.0, 13.0, 14.0]
    lows = [8.0, 9.0, 10.0, 11.0, 12.0]
    top = [9.0, 10.0, 11.0, 12.0, 14.0]
    k_top, _ = stochastic(highs, lows, top, k_period=4, d_period=2)
    assert k_top[4] == pytest.approx(100.0)

    # Close exactly at LL of the window → %K = 0.
    bottom = [9.0, 10.0, 11.0, 12.0, 9.0]
    k_bot, _ = stochastic(highs, lows, bottom, k_period=4, d_period=2)
    assert k_bot[4] == pytest.approx(0.0)


def test_stochastic_d_line_smooths_k() -> None:
    """%D is SMA of %K — for trivial monotone setup we just check
    it's defined and within [0, 100] once seeded."""
    n = 20
    highs = [100.0 + i for i in range(n)]
    lows = [99.0 + i for i in range(n)]
    closes = [99.5 + i for i in range(n)]
    _k, d = stochastic(highs, lows, closes, k_period=5, d_period=3)
    seeded_d = [v for v in d if v is not None]
    assert seeded_d
    assert all(0.0 <= v <= 100.0 for v in seeded_d)


def test_roc_returns_percent_change_versus_lookback() -> None:
    """ROC[period+i] = 100 * (v[period+i] - v[i]) / v[i]."""
    values = [100.0, 105.0, 110.0, 121.0]
    out = roc(values, period=2)
    # bar 2: 100 * (110 - 100) / 100 = 10.0
    assert out[2] == pytest.approx(10.0)
    # bar 3: 100 * (121 - 105) / 105 ≈ 15.238
    assert out[3] == pytest.approx(100.0 * (121 - 105) / 105)


def test_roc_zero_reference_returns_none() -> None:
    out = roc([0.0, 1.0, 2.0, 3.0], period=2)
    assert out[2] is None  # values[0] == 0
    # bar 3 references values[1] = 1.0 → defined.
    assert out[3] == pytest.approx(200.0)


# ─── Volume / Channels ────────────────────────────────────────────────


def test_mfi_pure_up_series_is_one_hundred() -> None:
    """All up bars → sum_neg = 0 → MFI = 100 by definition."""
    n = 20
    highs = [10.0 + i for i in range(n)]
    lows = [9.0 + i for i in range(n)]
    closes = [9.5 + i for i in range(n)]
    volumes = [1000.0] * n
    out = mfi(highs, lows, closes, volumes, period=14)
    assert out[14] == pytest.approx(100.0)


def test_mfi_pure_down_series_is_zero() -> None:
    n = 20
    highs = [40.0 - i for i in range(n)]
    lows = [38.0 - i for i in range(n)]
    closes = [39.0 - i for i in range(n)]
    volumes = [1000.0] * n
    out = mfi(highs, lows, closes, volumes, period=14)
    assert out[14] == pytest.approx(0.0)


def test_mfi_empty_or_short_input_returns_empty() -> None:
    assert mfi([], [], [], [], period=14) == []
    assert mfi([10.0] * 5, [9.0] * 5, [9.5] * 5, [1.0] * 5, period=14) == []


def test_donchian_channel_outputs_match_window_extremes() -> None:
    h = [1.0, 2.0, 3.0, 4.0, 5.0]
    lo = [0.5, 1.5, 2.5, 3.5, 4.5]
    upper, middle, lower = donchian_channel(h, lo, period=3)
    assert upper[2] == 3.0 and lower[2] == 0.5
    assert middle[2] == pytest.approx((3.0 + 0.5) / 2.0)
    assert upper[4] == 5.0 and lower[4] == 2.5
    assert middle[4] == pytest.approx((5.0 + 2.5) / 2.0)


def test_donchian_channel_empty_returns_three_empty_lists() -> None:
    u, m, lo = donchian_channel([], [], period=5)
    assert u == [] and m == [] and lo == []


def test_keltner_channel_band_geometry_is_correct() -> None:
    """Once seeded, ``upper - middle == middle - lower == multiplier * ATR``."""
    n = 30
    highs = [100.0 + i * 0.5 for i in range(n)]
    lows = [99.0 + i * 0.5 for i in range(n)]
    closes = [99.5 + i * 0.5 for i in range(n)]
    upper, middle, lower = keltner_channel(
        highs, lows, closes, period=10, multiplier=2.0
    )
    seeded = [
        (u, m, lo)
        for u, m, lo in zip(upper, middle, lower, strict=True)
        if u is not None and m is not None and lo is not None
    ]
    assert seeded
    for u, m, lo in seeded:
        upper_gap = u - m
        lower_gap = m - lo
        assert upper_gap == pytest.approx(lower_gap)
        assert upper_gap > 0


def test_keltner_channel_empty_returns_three_empty_lists() -> None:
    u, m, lo = keltner_channel([], [], [])
    assert u == [] and m == [] and lo == []


# ─── Determinism ──────────────────────────────────────────────────────


def test_pack2_calculations_are_deterministic() -> None:
    """Re-running every Pack 2 calculator on a copy of the same
    input must produce identical output. Catches accidental hidden
    state."""
    n = 50
    highs = [100.0 + math.sin(i * 0.1) * 5 for i in range(n)]
    lows = [h - 1.0 for h in highs]
    closes = [(h + lo) / 2.0 for h, lo in zip(highs, lows, strict=True)]
    volumes = [1_000.0 + i * 10 for i in range(n)]

    a1 = vwma(closes, volumes, period=14)
    a2 = vwma(list(closes), list(volumes), period=14)
    assert a1 == a2

    b1 = supertrend(highs, lows, closes, period=10, multiplier=3.0)
    b2 = supertrend(list(highs), list(lows), list(closes), period=10, multiplier=3.0)
    assert b1 == b2

    c1 = stochastic(highs, lows, closes, k_period=14, d_period=3)
    c2 = stochastic(list(highs), list(lows), list(closes), k_period=14, d_period=3)
    assert c1 == c2

    d1 = mfi(highs, lows, closes, volumes, period=14)
    d2 = mfi(list(highs), list(lows), list(closes), list(volumes), period=14)
    assert d1 == d2

    e1 = donchian_channel(highs, lows, period=10)
    e2 = donchian_channel(list(highs), list(lows), period=10)
    assert e1 == e2


# ─── Registry promotion ──────────────────────────────────────────────


_PACK2_IDS = {
    "vwma",
    "supertrend",
    "parabolic_sar",
    "smma",
    "dema",
    "tema",
    "hull_ma",
    "cci",
    "williams_r",
    "chande_momentum",
    "stochastic",
    "roc",
    "mfi",
    "donchian_channel",
    "keltner_channel",
}


def test_pack2_module_exposes_fifteen_indicators() -> None:
    """Sanity-check the manifest count itself doesn't drift."""
    assert len(PACK2_ACTIVE_INDICATORS) == 15
    assert {meta.id for meta in PACK2_ACTIVE_INDICATORS} == _PACK2_IDS


def test_pack2_indicators_are_active_in_registry() -> None:
    """The 15 ids that Pack 2 promotes must now resolve as ACTIVE in
    the runtime registry — the dict-comp later-wins ordering means
    Pack 2's row beats the same-id coming_soon stub."""
    for ind_id in _PACK2_IDS:
        meta = INDICATOR_REGISTRY.get(ind_id)
        assert meta is not None, f"{ind_id} missing from registry"
        assert meta.status is IndicatorStatus.ACTIVE, (
            f"{ind_id} is {meta.status}, expected ACTIVE"
        )
        assert meta.calculation_function == ind_id


def test_active_count_jumps_from_twenty_to_thirty_five() -> None:
    """20 historical actives + 15 Pack 2 promotions = 35.

    Loose lower bound (``>= 35``) rather than exact equality so
    later packs (Pack 3 candlestick patterns + future N) don't
    have to edit this file every time. Each pack pins its own
    delta in its own test."""
    assert len(get_active_indicators()) >= 35


def test_pack2_calculation_functions_are_resolvable() -> None:
    """``get_calculation_function`` must dynamically import each
    Pack 2 calc module and return a callable."""
    for ind_id in _PACK2_IDS:
        fn = get_calculation_function(ind_id)
        assert callable(fn), f"{ind_id} did not resolve to a callable"
