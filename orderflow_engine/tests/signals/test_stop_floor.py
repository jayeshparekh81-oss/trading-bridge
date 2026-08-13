"""R-stability: minimum stop distance + buffer-in-ticks (2026-07-16).

The thesis stop is the nearest structural level, but a dense level ladder (entries
fire NEAR levels by design) let the stop sit ~0 pts from entry -> near-zero R ->
exploding R-multiples (measured: NIFTY_FUT 07-15 stops from 0.11pt to 50pt; 07-16
min 0.02pt). Fix: never place the stop closer than max(min_stop_atr*ATR,
min_stop_pct%*entry); keep the structural stop when it is WIDER. Also: the buffer is
now TICKS*tick_size, not raw price.
"""

from __future__ import annotations

from types import SimpleNamespace

from signals.config import SignalConfig
from signals.exits import build_exit_plan


class _Reg:
    """Minimal LevelRegistry stand-in: .levels() -> objects with .price."""
    def __init__(self, prices):
        self._p = [SimpleNamespace(price=p) for p in prices]

    def levels(self):
        return self._p


def _ctx(price, prices, atr):
    return SimpleNamespace(price=price, registry=_Reg(prices), atr=atr)


# ATR 20 -> floor = max(0.3*20, 0.03%*24000) = max(6.0, 7.2) = 7.2 pts (pct backstop binds)
FLOOR_20 = 7.2


def test_floor_binds_when_structural_too_tight_long():
    cfg = SignalConfig({})
    ctx = _ctx(24000.0, [23999.0], atr=20.0)         # level 1pt below -> structural ~1pt
    plan = build_exit_plan(ctx, cfg, "long")
    assert abs(plan.r_value - FLOOR_20) < 1e-6        # floored to 7.2, not ~1
    assert plan.stop_source == "floor"
    assert plan.stop < ctx.price                      # stop below entry (long)


def test_structural_used_when_wider_than_floor_long():
    cfg = SignalConfig({})
    ctx = _ctx(24000.0, [23950.0], atr=20.0)          # level 50pt below >> floor
    plan = build_exit_plan(ctx, cfg, "long")
    # structural = 23950 - buf(2 ticks * 0.05 = 0.10) = 23949.90 -> r = 50.10
    assert abs(plan.r_value - 50.10) < 1e-6
    assert plan.stop_source == "registry"


def test_floor_binds_when_structural_too_tight_short():
    cfg = SignalConfig({})
    ctx = _ctx(24000.0, [24001.0], atr=20.0)          # level 1pt above
    plan = build_exit_plan(ctx, cfg, "short")
    assert abs(plan.r_value - FLOOR_20) < 1e-6
    assert plan.stop_source == "floor"
    assert plan.stop > ctx.price                      # stop above entry (short)


def test_structural_used_when_wider_than_floor_short():
    cfg = SignalConfig({})
    ctx = _ctx(24000.0, [24050.0], atr=20.0)
    plan = build_exit_plan(ctx, cfg, "short")
    assert abs(plan.r_value - 50.10) < 1e-6           # 24050 + 0.10 - 24000
    assert plan.stop_source == "registry"


def test_stop_never_closer_than_floor_across_a_ladder():
    """Whatever the nearest level, the resulting stop is never inside the floor."""
    cfg = SignalConfig({})
    for lvl in (23999.5, 23995.0, 23990.0, 23960.0, 23900.0):
        for atr in (10.0, 20.0, 40.0):
            ctx = _ctx(24000.0, [lvl], atr=atr)
            floor = max(0.3 * atr, 0.03 / 100.0 * 24000.0)
            plan = build_exit_plan(ctx, cfg, "long")
            assert plan.r_value >= floor - 1e-6


def test_buffer_is_ticks_not_raw_price():
    """thesis_stop_buffer_ticks=2 * tick_size 0.05 = 0.10, NOT 2.0 (the old raw-price bug)."""
    cfg = SignalConfig({})
    ctx = _ctx(24000.0, [23950.0], atr=1.0)           # atr tiny so floor (~7.2) < structural 50
    plan = build_exit_plan(ctx, cfg, "long")
    # stop sits 0.10 below the level (2 ticks), not 2.0
    assert abs(plan.stop - 23949.90) < 1e-6


def test_pct_backstop_when_atr_absent():
    """ATR None (first bar) -> floor falls back to min_stop_pct% of entry."""
    cfg = SignalConfig({})
    ctx = _ctx(24000.0, [23999.0], atr=None)
    plan = build_exit_plan(ctx, cfg, "long")
    assert abs(plan.r_value - (0.03 / 100.0 * 24000.0)) < 1e-6   # 7.2pt
