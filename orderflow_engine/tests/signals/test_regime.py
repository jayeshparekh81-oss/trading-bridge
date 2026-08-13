"""Regime module + asymmetric gate (Module R6)."""

from __future__ import annotations

from signals.config import SignalConfig
from signals.regime import apply_asymmetric, compute_regime
from tests.signals.fixtures import make_ctx

CFG = SignalConfig({})


def test_vix_bands():
    assert compute_regime(make_ctx(vix=10.0), CFG).vol_band == "low"
    assert compute_regime(make_ctx(vix=15.0), CFG).vol_band == "normal"
    assert compute_regime(make_ctx(vix=20.0), CFG).vol_band == "high"
    assert compute_regime(make_ctx(vix=None), CFG).vol_band == "normal"


def test_trend_direction():
    assert compute_regime(make_ctx(ma_slope=1.0), CFG).direction == "bull"
    assert compute_regime(make_ctx(ma_slope=-1.0), CFG).direction == "bear"
    assert compute_regime(make_ctx(ma_slope=0.0), CFG).direction == "neutral"


def test_participant_override_and_conflict():
    long_bias = SignalConfig({"signal": {"regime": {"participant_oi_bias": "long"}}})
    # participant long + neutral trend -> bull
    assert compute_regime(make_ctx(ma_slope=0.0), long_bias).direction == "bull"
    # participant long vs bear trend -> conflict -> neutral
    assert compute_regime(make_ctx(ma_slope=-1.0), long_bias).direction == "neutral"


def test_asymmetric_gate_escalates_countertrend():
    ag = CFG.asymmetric_gate
    # strong bull -> short threshold escalates by the penalty (+10)
    assert apply_asymmetric(30.0, "short", "bull", ag) == 40.0
    # longs in bull are unaffected
    assert apply_asymmetric(30.0, "long", "bull", ag) == 30.0
    # strong bear -> long escalates
    assert apply_asymmetric(30.0, "long", "bear", ag) == 40.0


def test_asymmetric_gate_can_disable_countertrend():
    ag = dict(CFG.asymmetric_gate)
    ag["disable_countertrend"] = True
    assert apply_asymmetric(30.0, "short", "bull", ag) >= 999_999


def test_asymmetric_gate_off():
    ag = {"enabled": False}
    assert apply_asymmetric(30.0, "short", "bull", ag) == 30.0
