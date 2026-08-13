"""Confluence scorer: long/short sums, toggles, weights (Module R6)."""

from __future__ import annotations

from signals.config import SignalConfig
from signals.scorer import evaluate, score_side
from tests.signals.fixtures import make_ctx


def _long_ctx():
    return make_ctx(recent_big_print_side=1, cvd_slope=2.0, velocity_spike=True,
                    bar_delta=50, vwap=101.0, vwap_bands={"lower_1": 100.5},
                    val=100.0, ib_low=99.8, regime_direction="bull")


def test_long_score_sums_enabled_components():
    r = score_side(_long_ctx(), SignalConfig({}), "long")
    # big_print 20 + vwap_value_location 15 + cvd_confirm 10 + velocity 5 + regime 5 = 55
    assert r["score"] == 55.0
    assert r["threshold"] == 999.0                 # inert
    assert r["breakdown"]["big_print"]["contribution"] == 20.0


def test_disabled_component_contributes_zero():
    cfg = SignalConfig({"signal": {"components": {"big_print": {"enabled": False, "weight": 20}}}})
    r = score_side(_long_ctx(), cfg, "long")
    assert r["breakdown"]["big_print"]["contribution"] == 0.0
    assert r["score"] == 35.0                       # 55 - 20


def test_weight_override_scales_contribution():
    cfg = SignalConfig({"signal": {"components": {"cvd_confirm": {"enabled": True, "weight": 30}}}})
    r = score_side(_long_ctx(), cfg, "long")
    assert r["breakdown"]["cvd_confirm"]["contribution"] == 30.0


def test_short_side_independent():
    r = evaluate(_long_ctx(), SignalConfig({}))
    assert r["long"]["score"] == 55.0
    assert r["short"]["score"] == 0.0               # long-favorable ctx -> short empty


def test_short_weight_overrides():
    cfg = SignalConfig({"signal": {"short": {"weight_overrides": {"cvd_confirm": 50}}}})
    ctx = make_ctx(cvd_slope=-2.0)                   # short cvd_confirm active
    assert score_side(ctx, cfg, "short")["breakdown"]["cvd_confirm"]["contribution"] == 50.0
