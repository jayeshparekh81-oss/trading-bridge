"""Confluence component activations (Module R6)."""

from __future__ import annotations

from levels.registry import LevelRegistry

from signals import components as C
from signals.config import SignalConfig
from tests.signals.fixtures import make_ctx

CFG = SignalConfig({})


def test_big_print_side():
    assert C.big_print(make_ctx(recent_big_print_side=1), CFG, "long") == 1.0
    assert C.big_print(make_ctx(recent_big_print_side=1), CFG, "short") == 0.0
    assert C.big_print(make_ctx(recent_big_print_side=-1), CFG, "short") == 1.0


def test_cvd_confirm_direction():
    assert C.cvd_confirm(make_ctx(cvd_slope=2.0), CFG, "long") == 1.0
    assert C.cvd_confirm(make_ctx(cvd_slope=2.0), CFG, "short") == 0.0
    assert C.cvd_confirm(make_ctx(cvd_slope=-2.0), CFG, "short") == 1.0


def test_stub_components_neutral_until_depth():
    ctx = make_ctx(book_ofi=None, queue_imbalance=None)
    assert C.book_ofi(ctx, CFG, "long") == 0.0
    assert C.queue_imbalance(ctx, CFG, "long") == 0.0


def test_vwap_value_location_long():
    # price at/below lower band (0.5) AND near VAL (0.5) -> 1.0
    ctx = make_ctx(price=99.0, vwap=101.0, vwap_bands={"lower_1": 99.5, "upper_1": 102.5},
                   val=99.0, ib_low=98.5)
    assert C.vwap_value_location(ctx, CFG, "long") == 1.0
    # short mirror not active on a long-value context
    assert C.vwap_value_location(ctx, CFG, "short") == 0.0


def test_level_zone_graded_by_proximity():
    reg = LevelRegistry(1, "X", "d")
    reg.add("POC", 100.0)
    at = make_ctx(price=100.0, registry=reg)         # exactly at -> 1.0
    near = make_ctx(price=102.5, registry=reg)        # half a band away (ticks=5) -> 0.5
    assert C.level_zone(at, CFG, "long") == 1.0
    assert C.level_zone(near, CFG, "long") == 0.5


def test_tape_velocity_aligned():
    up = make_ctx(velocity_spike=True, bar_delta=50)
    assert C.tape_velocity(up, CFG, "long") == 1.0
    assert C.tape_velocity(make_ctx(velocity_spike=False, bar_delta=50), CFG, "long") == 0.0


def test_regime_component():
    assert C.regime(make_ctx(regime_direction="bull"), CFG, "long") == 1.0
    assert C.regime(make_ctx(regime_direction="bull"), CFG, "short") == 0.0
    assert C.regime(make_ctx(regime_direction="bear"), CFG, "short") == 1.0


def test_big_print_graded_on_strength():
    import signals.components as C2
    from tests.signals.fixtures import make_ctx
    cfg = None
    # a full-strength aligned print -> 1.0; a weak-tail one -> its strength; wrong side -> 0
    assert C2.big_print(make_ctx(recent_big_print_side=1, recent_big_print_strength=1.0), cfg, "long") == 1.0
    assert C2.big_print(make_ctx(recent_big_print_side=1, recent_big_print_strength=0.3), cfg, "long") == 0.3
    assert C2.big_print(make_ctx(recent_big_print_side=1, recent_big_print_strength=0.9), cfg, "short") == 0.0
