"""Writes CP5_calibration.md from cp5_calibration.json (second pass) and cp5_calibration_firstpass.json."""
import sys, json, numpy as np
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); import first_passage as FP
c = json.loads((D3 / "cp5_calibration.json").read_text()); f = json.loads((D3 / "cp5_calibration_firstpass.json").read_text()); TOL = c["tolerance_pp"]
def grid_md(g):
    out = ["| stop \\ target | " + " | ".join(f"{b}σ" for b in FP.K) + " |", "|---|" + "---|" * len(FP.K)]
    for a in FP.K: out.append(f"| {a}σ | " + " | ".join(f"{g[f'{a}:{b}']['win']*100:.1f} / {a/(a+b)*100:.1f} (n={g[f'{a}:{b}']['n_resolved']})" for b in FP.K) + " |")
    return "\n".join(out)
sec = []
for seed in ("101", "202"):
    s = c["synthetic"][seed]; d = c["drift"][seed]; s1 = f["synthetic"][seed]; d1 = f["drift"][seed]
    sec.append(f"\n### Seed {seed}\n**Driftless walk, second pass (60 sessions × 120 random events):** worst |recovered − a/(a+b)| = **{s['worst_abs_dev_pp']:.2f} pp** (tolerance {TOL} pp) → {'PASS' if s['worst_abs_dev_pp'] <= TOL else 'FAIL'}; first pass (30 × 60) was {s1['worst_abs_dev_pp']:.2f} pp. Median σ_1m/σ_step = {s['sigma_1m_over_sigma_step_median']:.1f}.\nRecovered / theory (%, n resolved):\n" + grid_md(s["grid"]))
    rows = ["| pair | no-drift theory | closed form with drift | recovered (2nd pass) | n resolved | recovered (1st pass, censoring not excluded) |", "|---|---|---|---|---|---|"]
    for k_, r in d["rows"].items(): rows.append(f"| {k_} | {r['theory_no_drift']*100:.1f}% | {r['theory_with_drift']*100:.1f}% | {r['recovered']*100:.1f}% | {r['n_resolved']} | {d1['rows'][k_]['recovered']*100:.1f}% |")
    sec.append(f"**Injected drift (+0.01·σ_step per 200 ms step; events with ≥ 2 h to session end; unresolved share on scored pairs {[round(v*100,1) for v in d.get('unresolved_share_scored_pairs', {}).values()]} %):** worst |recovered − closed form| = **{d['worst_abs_dev_pp']:.2f} pp** → {'PASS' if d['worst_abs_dev_pp'] <= TOL else 'FAIL'}; first pass (all events, censoring included) was {d1['worst_abs_dev_pp']:.2f} pp.\n" + "\n".join(rows))
    r = c["randx"][seed]; ps = [r["cells"][i][k]["p_two_sided"] for i in r["cells"] for k in r["cells"][i]]
    sec.append(f"**RANDX on real discovery tape:** cells passing the pass bar {sum(v.startswith('PASS') for v in r['verdicts'].values())}/4; p < 0.05 on {sum(p < 0.05 for p in ps)}/8 instrument-tests; min p {min(ps):.4f}; lifts (pp): " + ", ".join(f"{i[:5]} {k} {r['cells'][i][k]['lift_pp']:+.1f}" for i in r["cells"] for k in r["cells"][i]))
ok_s = all(c["synthetic"][s]["worst_abs_dev_pp"] <= TOL for s in ("101", "202")); ok_d = all(c["drift"][s]["worst_abs_dev_pp"] <= TOL for s in ("101", "202")); ok_r = all(sum(v.startswith("PASS") for v in c["randx"][s]["verdicts"].values()) == 0 for s in ("101", "202"))
doc = f"""# CP5 (run 3) — CALIBRATION of the first-passage engine

Harness: run-1/2 fixes kept (seed sequences [seed, ·] → non-overlapping seeds 101 / 202; deterministic pickers; recovery tested on random events, never on the real signal). Synthetic driftless Gaussian walk at 5 Hz (σ_step = 0.3 pts, 6.25-h sessions) pushed through the REAL engine (trailing σ_1m + joint object); random events with random orientation; recovered hit-first win rate vs a/(a+b) on the full 7×7 grid; tolerance ±{TOL} pp (PREREG3 §9).

## Self-check (why there are two passes)
- `self-check found`: the first pass (30 sessions × 60 events, ~1,790 resolved per cell) had a binomial SE ≈ 1.2 pp per cell, so the worst of 49 correlated cells breached the 3-pp tolerance on seed 202 (3.76 pp) while seed 101's worst was 2.08 pp with no directional pattern; `fixed by` quadrupling the events (60 × 120, SE ≈ 0.55 pp) with the tolerance and seeds unchanged. The first pass is kept in `cp5_calibration_firstpass.json`.
- `self-check found`: the injected-drift comparison used a closed form that assumes no right-censoring; under drift, trades left unresolved at session end are not random with respect to the outcome, so the resolved-only rate exceeded the closed form by 2–5 pp on both seeds, growing with barrier size — the censoring effect itself; `fixed by` comparing on events with ≥ 2 h to session end (unresolved share ≈ 0), closed form unchanged.
""" + "\n".join(sec) + f"""

## Gate
Driftless grid within tolerance on both seeds: {'YES' if ok_s else 'NO'}; injected drift recovered within tolerance with the correct direction on both seeds: {'YES' if ok_d else 'NO'}; RANDX passes nothing: {'YES' if ok_r else 'NO'}. **CP5 {'GREEN' if ok_s and ok_d and ok_r else 'RED'}.**
"""
(D3 / "CP5_calibration.md").write_text(doc); print(f"  CP5_calibration.md written; gate {'GREEN' if ok_s and ok_d and ok_r else 'RED'}")
