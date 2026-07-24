"""SHADOW-TRIO RANKING PROBE (2026-07-24) — IN-SAMPLE EXPLORATION — NOT A REGISTERED RESULT.

FROZEN QUESTION (exactly 3 comparisons): do the AS-COMPUTED activations of book_ofi,
queue_imbalance, and pain_map RANK the net-R outcomes of the already-priced size-100
delta+vwap fires? Spearman rho only, per component per instrument, vs a 1000-permutation
shuffled null (seed 20260724). No thresholds, no combos, no scans. big_print excluded
(needs a threshold choice — stays R2-01).

Mechanics:
  * One replay per burned depth-day with a SCRATCH tape yaml (depth.ofi_enabled: true so
    book_ofi computes; qi + pain_map flow via the merged shadow wiring). Committed configs
    untouched — the scratch yaml lives in the probe's state dir.
  * Activations read from each fired candidate's own scored-row breakdown (side-specific).
  * Fires are priced IN-PASS with pricing.depth_ofi_enabled forced False so exits replicate
    the frozen baseline exactly (momentum-death ofi_flip stays dormant; stops/targets are
    OFI-independent). Join is therefore internal (activation and net-R from the same row);
    integrity is validated against the cached dv_result per-day gross/net sums.
  * Anchored per-day medians come from the cached size-100 candidate stubs (delta_al and
    vwap_dist_al are OFI-independent, so the stubs transfer exactly).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional, Sequence

from research.delta_vwap_evaluator import (
    DayCapture, median_delta_al, price_candidate, rule_decisions,
)

COMPONENTS = ("book_ofi", "queue_imbalance", "pain_map")
SEED = 20260724


# ============================ probe capture ==================================
def probe_capture_day(day: str, *, root: str | Path = ".",
                      config_path: str | Path) -> tuple[DayCapture, dict]:
    """capture_day + per-candidate activations from the breakdown. Returns
    (cap, acts) with acts[(sid, ts_ns, side)] = {component: activation}.
    cap.depth_ofi_enabled is FORCED False so price_candidate replicates the
    frozen-baseline exits (see module doc)."""
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from signals.config import load_signal_config
    from signals.pipeline import build_pipeline

    dd = Path(root) / "data" / day
    multi, parts = build_pipeline(dd, load_signal_config(config_path),
                                  config_path=config_path)
    sig, tape, meta = parts["signal"], parts["tape"], parts["meta"]
    ctxs: dict = {}
    costs: dict = {}
    orig_bc = sig._build_context
    def _bc(sid, bar, ts):
        c = orig_bc(sid, bar, ts)
        ctxs[(sid, c.ts_ns)] = c
        return c
    sig._build_context = _bc
    orig_ev = sig._evaluate
    def _ev(sid, bar, ts):
        orig_ev(sid, bar, ts)
        c = ctxs.get((sid, bar["end_ts_ns"]))
        if c is not None:
            for side in sig.sides:
                costs[(sid, c.ts_ns, side)] = sig._capture_cost_inputs(c, side)
    sig._evaluate = _ev
    ReplayEngine(ReplaySource(dd)).drive(multi, speed="max")
    sig.finalize()

    bars: dict = {}
    for b in tape.bar_rows:
        if b["bar_type"] == "tick":
            bars.setdefault(b["security_id"], []).append(b)
    for arr in bars.values():
        arr.sort(key=lambda b: b["end_ts_ns"])
    sid_by = {m["symbol"]: s for s, m in meta.items()}
    cands, acts = [], {}
    for r in sig.rows:
        sid = sid_by.get(r["instrument"])
        c = ctxs.get((sid, r["ts_ns"]))
        sgn = 1 if r["side"] == "long" else -1
        cands.append({"ts_ns": r["ts_ns"], "sid": sid, "instrument": r["instrument"],
                      "side": r["side"], "fired": bool(r["fired"]), "score": r["score"],
                      "delta_al": (c.bar_delta * sgn) if c is not None else None,
                      "vwap_dist_al": ((c.price - c.vwap) * sgn)
                                      if (c is not None and c.vwap is not None) else None})
        bd = json.loads(r["breakdown"])
        acts[(sid, r["ts_ns"], r["side"])] = {k: bd[k]["activation"] for k in COMPONENTS}
    cap = DayCapture(day=day, candidates=cands, ctx=ctxs, bars=bars, cost_inputs=costs,
                     sig_cfg=sig.cfg, depth_ofi_enabled=False)   # False -> baseline exits
    return cap, acts


def probe_day(day: str, stubs: dict, *, root: str | Path = ".",
              config_path: str | Path,
              instruments: Sequence[str] = ("NIFTY_FUT", "BANKNIFTY_FUT")) -> dict:
    """One day's joined rows: per instrument, every priced rule-fire with its activations."""
    cap, acts = probe_capture_day(day, root=root, config_path=config_path)
    captures = {d: DayCapture(day=d, candidates=stubs[d]) for d in stubs if d < day}
    captures[day] = cap
    prior = sorted(d for d in stubs if d < day)
    out = {"label": "IN-SAMPLE EXPLORATION — NOT A REGISTERED RESULT", "day": day}
    for inst in instruments:
        dmed = median_delta_al(captures, prior, inst)
        rows = []
        for cand, fires in rule_decisions(cap, inst, dmed):
            if not fires:
                continue
            rec = price_candidate(cap, cand)
            if rec is None:
                continue
            a = acts.get((cand["sid"], cand["ts_ns"], cand["side"]), {})
            rows.append({"ts_ns": cand["ts_ns"], "side": cand["side"],
                         "gross": rec["realized_r"], "net": rec["realized_r_net"],
                         **{f"{k}_act": a.get(k) for k in COMPONENTS}})
        out[inst] = {"fires": rows,
                     "gross_sum": round(sum(r["gross"] for r in rows), 3),
                     "net_sum": round(sum(r["net"] for r in rows
                                          if r["net"] is not None), 3)}
    return out


# ============================ stats ==========================================
def _rank(v: Sequence[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) < 3:
        return None
    rx, ry = _rank(list(x)), _rank(list(y))
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx == 0 or dy == 0:
        return None                                    # a constant series cannot rank
    return num / (dx * dy)


def perm_percentile(x: Sequence[float], y: Sequence[float], *, n: int = 1000,
                    seed: int = SEED) -> Optional[dict]:
    """Real rho + its percentile within a shuffled-y null (fraction of null <= real)."""
    real = spearman(x, y)
    if real is None:
        return None
    rng = random.Random(seed)
    ys = list(y)
    null = []
    for _ in range(n):
        rng.shuffle(ys)
        r = spearman(x, ys)
        null.append(r if r is not None else 0.0)
    pct = 100.0 * sum(1 for r in null if r <= real) / len(null)
    return {"rho": round(real, 4), "null_pct": round(pct, 1), "n_perm": n}


def component_table(all_rows: dict[str, list[dict]]) -> list[dict]:
    """all_rows: instrument -> joined fire rows (across days). One output row per
    component x instrument: nonzero%, N joined, rho, null-percentile."""
    out = []
    for inst, rows in all_rows.items():
        for comp in COMPONENTS:
            pairs = [(r[f"{comp}_act"], r["net"]) for r in rows
                     if r.get(f"{comp}_act") is not None and r.get("net") is not None]
            n = len(pairs)
            nz = sum(1 for a, _ in pairs if abs(a) > 1e-9)
            nzr = round(100.0 * nz / n, 1) if n else None
            stats = None
            if n >= 3 and nz > 0:
                stats = perm_percentile([a for a, _ in pairs], [b for _, b in pairs])
            out.append({"instrument": inst, "component": comp, "n_joined": n,
                        "nonzero_pct": nzr,
                        "rho": stats["rho"] if stats else None,
                        "null_pct": stats["null_pct"] if stats else None,
                        "note": ("" if stats else
                                 ("~always 0 — cannot rank anything" if n and nz == 0
                                  else "insufficient data"))})
    return out
