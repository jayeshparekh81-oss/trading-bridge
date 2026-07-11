"""Sweep 2.0 (Module R6) — plateau-first calibration harness with a budget guard.

Sweeps <= 3 knobs (an explicit overfitting guard: more than 3 free params at once
is refused) and reports a PLATEAU analysis — we want a stable region where the
metric holds, not a lone sharp peak that won't survive live. ``run_fn`` is
injectable (tests pass a synthetic function; production passes a signal.run wrapper
over a day-set) so the harness is testable without a replay.
"""

from __future__ import annotations

from itertools import product

MAX_PARAMS = 3


def set_nested(d: dict, dotted: str, value) -> dict:
    cur = d
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value
    return d


def _overrides(combo: dict) -> dict:
    out: dict = {}
    for dotted, value in combo.items():
        set_nested(out, dotted, value)
    return {"signal": out}


def plateau_analysis(results: list[dict], rel_tol: float = 0.1) -> dict:
    """A plateau = combos whose metric is within rel_tol of the best. A robust
    result has >= 2 combos on the plateau (not a single spike)."""
    if not results:
        return {"best": None, "plateau_size": 0, "is_plateau": False}
    best = max(r["metric"] for r in results)
    band = abs(best) * rel_tol
    plateau = [r for r in results if r["metric"] >= best - band]
    return {"best": best, "plateau_size": len(plateau),
            "is_plateau": len(plateau) >= 2,
            "plateau_combos": [r["combo"] for r in plateau]}


def sweep(param_specs: list[tuple], run_fn, *, rel_tol: float = 0.1) -> dict:
    """param_specs: [(dotted_knob, [values]), ...] (<= 3). run_fn(overrides)->metric."""
    if len(param_specs) > MAX_PARAMS:
        raise ValueError(
            f"Sweep 2.0 budget guard: at most {MAX_PARAMS} params at once "
            f"(got {len(param_specs)}) — sweeping more is an overfitting risk.")
    names = [p[0] for p in param_specs]
    grids = [p[1] for p in param_specs]
    results = []
    for values in product(*grids):
        combo = dict(zip(names, values))
        metric = float(run_fn(_overrides(combo)))
        results.append({"combo": combo, "metric": metric})
    return {"results": results, "plateau": plateau_analysis(results, rel_tol),
            "params": names}
