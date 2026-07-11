"""Confluence scorer (Module R6) — long & short as first-class mirrors.

score(side) = Σ over ENABLED components of activation(component, ctx, side) * weight.
Each side has its own weights (short via weight_overrides) and its own fire
threshold. Returns the total plus a full per-component breakdown (glass box).
"""

from __future__ import annotations

from signals.components import COMPONENTS


def score_side(ctx, cfg, side: str) -> dict:
    breakdown = {}
    total = 0.0
    for name, fn in COMPONENTS.items():
        comp = cfg.component(name, side)
        act = float(fn(ctx, cfg, side))
        contrib = act * comp.weight if comp.enabled else 0.0
        breakdown[name] = {"activation": round(act, 6), "weight": comp.weight,
                           "enabled": comp.enabled, "contribution": round(contrib, 6)}
        total += contrib
    return {"side": side, "score": round(total, 6), "breakdown": breakdown,
            "threshold": cfg.fire_threshold(side)}


def evaluate(ctx, cfg) -> dict:
    """Score both sides independently."""
    return {"long": score_side(ctx, cfg, "long"),
            "short": score_side(ctx, cfg, "short")}
