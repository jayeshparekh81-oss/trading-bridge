"""Perturbation robustness test (Module R6).

Nudge each chosen knob by +/- delta and check the metric does not collapse — a
calibrated setting that only works at one exact value is overfit. ``run_fn`` is
injectable (same contract as sweep).
"""

from __future__ import annotations

from signals.sweep import set_nested


def _ov(knob: str, value) -> dict:
    out: dict = {}
    set_nested(out, knob, value)
    return {"signal": out}


def perturb(knob_deltas: list[tuple], run_fn, *, tolerance: float = 0.2) -> dict:
    """knob_deltas: [(dotted_knob, base_value, delta), ...]. Returns robustness."""
    results = []
    worst_drop = 0.0
    for knob, base, delta in knob_deltas:
        base_m = float(run_fn(_ov(knob, base)))
        for sign in (+1, -1):
            m = float(run_fn(_ov(knob, base + sign * delta)))
            drop = (base_m - m) / abs(base_m) if base_m else 0.0
            worst_drop = max(worst_drop, drop)
            results.append({"knob": knob, "value": base + sign * delta,
                            "metric": m, "drop_from_base": round(drop, 4)})
    return {"results": results, "worst_drop": round(worst_drop, 4),
            "robust": worst_drop <= tolerance, "tolerance": tolerance}
