"""CP5 (run 3, SECOND PASS — first pass kept in cp5_calibration_firstpass.json) — (1) SYNTHETIC driftless random walk through the REAL engine (trailing sigma + joint object): recovered
hit-first win rates vs a/(a+b) on the full 7x7 grid, tolerance +-3 pp; (2) INJECTED DRIFT vs the closed-form
P = (1-exp(-2*mu*a/s^2))/(1-exp(-2*mu*(a+b)/s^2)); (3) RANDX on real discovery tape (random events, matched null) must not
pass. Seeds 101 and 202 (seed sequences, non-overlapping)."""
import sys, json, numpy as np, pandas as pd
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); sys.path.insert(0, str(D3 / "scripts")); import first_passage as FP, scorer3 as S
STEP_S = 0.2; SESS_S = 6.25 * 3600; NSTEP = int(SESS_S / STEP_S); SIG_STEP = 0.3; N_SESS = 60; EV_PER_SESS = 120; TOL_PP = 3.0; MIN_CENSOR_S = 7200.0   # second pass: 4x events (SE ~0.55 pp), same tolerance; drift test on events with >= 2 h to session end (censoring ~0)
def synth_session(rng, mu=0.0):
    mid = 20000.0 + np.cumsum(rng.normal(mu, SIG_STEP, NSTEP)); ts_s = np.arange(NSTEP) * STEP_S + STEP_S
    bar_end_s = np.arange(5.0, SESS_S + 1e-9, 5.0); bi = np.searchsorted(ts_s, bar_end_s, side="right") - 1; bar_mid = mid[bi]
    sigma = FP.trailing_sigma(bar_mid); t_up, t_dn, censor, *_ = FP.joint_object(ts_s, mid, bar_end_s, bar_mid, sigma)
    return t_up, t_dn, censor, sigma
def grid_from(t_up, t_dn, ev, dirs):
    g = {}
    for ai, a in enumerate(FP.K):
        for bi_, b in enumerate(FP.K):
            t_t = np.where(dirs > 0, t_up[ev, bi_], t_dn[ev, bi_]); t_s = np.where(dirs > 0, t_dn[ev, ai], t_up[ev, ai]); res = ~(np.isnan(t_t) & np.isnan(t_s)); w = res & (np.nan_to_num(t_t, nan=np.inf) < np.nan_to_num(t_s, nan=np.inf))
            g[f"{a}:{b}"] = {"n_resolved": int(res.sum()), "win": float(w.sum() / max(res.sum(), 1))}
    return g
def drift_theory(a, b, mu, s2): 
    x = 2 * mu / s2; return (1 - np.exp(-x * a)) / (1 - np.exp(-x * (a + b)))
out = {"tolerance_pp": TOL_PP, "synthetic": {}, "drift": {}, "randx": {}}
for seed in (101, 202):
    rng = np.random.default_rng([seed, 0]); TU, TD, EV, DIRS, SIG = [], [], [], [], []
    for s in range(N_SESS):
        t_up, t_dn, censor, sigma = synth_session(rng); ok = np.flatnonzero(~np.isnan(censor) & ~np.isnan(sigma)); pick = np.sort(rng.choice(ok, size=EV_PER_SESS, replace=False))
        TU.append(t_up); TD.append(t_dn); EV.append(pick + s * len(censor)); DIRS.append(rng.choice([-1, 1], size=EV_PER_SESS)); SIG.append(sigma[pick])
    TU = np.vstack(TU); TD = np.vstack(TD); EV = np.concatenate(EV); DIRS = np.concatenate(DIRS); g = grid_from(TU, TD, EV, DIRS)
    worst = max(abs(v["win"] - a / (a + b)) * 100 for k_, v in g.items() for a, b in [tuple(map(float, k_.split(":")))]); out["synthetic"][seed] = {"grid": g, "worst_abs_dev_pp": worst, "sigma_1m_over_sigma_step_median": float(np.median(np.concatenate(SIG)) / SIG_STEP)}
    print(f"\n  SYNTHETIC driftless walk, seed {seed}: {N_SESS} sessions x {EV_PER_SESS} random events; worst |recovered - theory| = {worst:.2f} pp (tolerance {TOL_PP} pp) -> {'PASS' if worst <= TOL_PP else 'FAIL'}; median sigma_1m/sigma_step = {out['synthetic'][seed]['sigma_1m_over_sigma_step_median']:.1f}")
    print("    stop\\target " + " ".join(f"{b:>11}" for b in FP.K))
    for a in FP.K: print(f"    {a:>10}  " + " ".join(f"{g[f'{a}:{b}']['win']*100:5.1f}/{a/(a+b)*100:4.1f}" for b in FP.K) + "   (recovered/theory %)")
    # injected drift: mu per step = +0.01 sigma_step; all events oriented +1; compare with closed form in step units (a,b in sigma_1m -> steps)
    rng = np.random.default_rng([seed, 1]); mu = 0.01 * SIG_STEP; TU, TD, EV, SIGS = [], [], [], []
    for s in range(N_SESS):
        t_up, t_dn, censor, sigma = synth_session(rng, mu=mu); ok = np.flatnonzero(~np.isnan(censor) & ~np.isnan(sigma) & (censor >= MIN_CENSOR_S)); pick = np.sort(rng.choice(ok, size=EV_PER_SESS, replace=False))
        TU.append(t_up); TD.append(t_dn); EV.append(pick + s * len(censor)); SIGS.append(sigma[pick])
    TU = np.vstack(TU); TD = np.vstack(TD); EV = np.concatenate(EV); SIGS = np.concatenate(SIGS); g = grid_from(TU, TD, EV, np.ones(len(EV), int)); sig_ratio = float(np.median(SIGS) / SIG_STEP)
    rows = {}; worst_d = 0
    for a, b in S.PAIRS + [(1.0, 2.0), (0.5, 0.5)]:
        th = drift_theory(a * sig_ratio, b * sig_ratio, mu / SIG_STEP, 1.0); rec = g[f"{a}:{b}"]["win"]; rows[f"{a}:{b}"] = {"theory_no_drift": a / (a + b), "theory_with_drift": float(th), "recovered": rec, "n_resolved": g[f"{a}:{b}"]["n_resolved"]}; worst_d = max(worst_d, abs(rec - th) * 100)
    out["drift"][seed] = {"mu_per_step_over_sigma_step": 0.01, "rows": rows, "worst_abs_dev_pp": worst_d}
    unres = {k_: 1 - g[k_]["n_resolved"] / len(EV) for k_ in g}; out["drift"][seed]["unresolved_share_scored_pairs"] = {f"{a}:{b}": unres[f"{a}:{b}"] for a, b in S.PAIRS}
    print(f"  INJECTED DRIFT seed {seed} (mu = +0.01 sigma_step per step; events with >= {MIN_CENSOR_S:.0f} s to close; unresolved share on scored pairs {[round(unres[f'{a}:{b}']*100,1) for a,b in S.PAIRS]} %): worst |recovered - closed form| = {worst_d:.2f} pp -> {'PASS' if worst_d <= TOL_PP else 'FAIL'}")
    for k_, r in rows.items(): print(f"    pair {k_}: no-drift {r['theory_no_drift']*100:5.1f}%  with-drift theory {r['theory_with_drift']*100:5.1f}%  recovered {r['recovered']*100:5.1f}% (n={r['n_resolved']})")
# RANDX on real discovery tape
cp2 = json.loads((D3 / "cp2_baseline.json").read_text()); q = json.loads((D3 / "QUARANTINE.json").read_text()); FD = D3 / "features_discovery"
for seed in (101, 202):
    res = {}
    for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
        df = pd.concat([pd.read_parquet(FD / f"{d}_{inst}.parquet").assign(date=d) for d in q["discovery"]], ignore_index=True)
        real = np.flatnonzero(df.F1_thin.to_numpy(bool)); slot = df.slot.to_numpy(); sb = df.sbucket.to_numpy(); usable = df.usable.to_numpy(bool) & (df["dir"].to_numpy() == 0)
        rng = np.random.default_rng([seed, 7]); rand = []
        for (s_, b_), n in pd.Series(list(zip(slot[real], sb[real]))).value_counts().items(): pool = np.flatnonzero(usable & (slot == s_) & (sb == b_)); rand.append(rng.choice(pool, size=min(n, len(pool)), replace=False))
        rand = np.sort(np.concatenate(rand)); dir_all = np.zeros(len(df), int); dir_all[rand] = rng.choice([-1, 1], size=len(rand))
        res[inst] = {f"{a}:{b}": S.score_cell(df, rand, dir_all, a, b, seed=seed, nb=500) for a, b in S.PAIRS}
    verdicts = {k: S.cell_verdict(res["NIFTY_FUT"][k], res["BANKNIFTY_FUT"][k]) for k in res["NIFTY_FUT"]}; ps = [res[i][k]["p_two_sided"] for i in res for k in res[i]]
    out["randx"][seed] = {"cells": res, "verdicts": verdicts}
    print(f"  RANDX real tape seed {seed}: passes {sum(v.startswith('PASS') for v in verdicts.values())}/4 cells; p<0.05 on {sum(p < 0.05 for p in ps)}/8 instrument-tests; min p {min(ps):.4f}; lifts pp: " + ", ".join(f"{i[:5]} {k} {res[i][k]['lift_pp']:+.1f}" for i in res for k in res[i]))
(D3 / "cp5_calibration.json").write_text(json.dumps(out, indent=1, default=float)); print("  written cp5_calibration.json")
