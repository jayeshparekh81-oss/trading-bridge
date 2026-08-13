"""Pain-map lens (Module R6) — trapped pressure + weight-0 inertness."""

from __future__ import annotations

from signals.config import SignalConfig
from signals.painmap import trapped_pressure
from signals.scorer import score_side
from tests.signals.fixtures import make_ctx


def test_trapped_shorts_fuel_upside():
    # short_buildup (trapped shorts) + short_covering -> long (upside) fuel
    ctx = make_ctx(buildup_matrix={"short_buildup": 6, "short_covering": 2, "long_buildup": 2})
    assert trapped_pressure(ctx, "long") > trapped_pressure(ctx, "short")


def test_trapped_longs_fuel_downside():
    ctx = make_ctx(buildup_matrix={"long_buildup": 7, "long_unwinding": 3, "short_buildup": 0})
    assert trapped_pressure(ctx, "short") > trapped_pressure(ctx, "long")


def test_empty_matrix_zero():
    assert trapped_pressure(make_ctx(buildup_matrix={}), "long") == 0.0


def test_pain_map_weight_zero_contributes_nothing():
    ctx = make_ctx(buildup_matrix={"short_buildup": 10})   # strong long pressure
    r = score_side(ctx, SignalConfig({}), "long")
    assert r["breakdown"]["pain_map"]["activation"] > 0     # computed
    assert r["breakdown"]["pain_map"]["contribution"] == 0.0  # but INERT (weight 0)
