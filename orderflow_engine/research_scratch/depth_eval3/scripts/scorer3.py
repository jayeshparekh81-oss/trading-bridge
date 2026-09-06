"""scorer3.py — hit-first scoring per PREREG3: orientation by side, (stop=a*sigma, target=b*sigma) from the joint object,
explicit censoring, volatility- AND time-of-day-matched random baseline (random orientation per draw), seed sequences
[seed, b] (non-overlapping), deterministic pickers. Third-look bar: alpha = 0.05/54 on BOTH instruments, same sign, n_resolved >= 100."""
import json, numpy as np, pandas as pd
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent
B = 2000; SEED = 20260907; N_HYP_ALL_RUNS = 54; ALPHA = 0.05 / N_HYP_ALL_RUNS; MIN_RESOLVED = 100; THIN_S = 300
PAIRS = [(1.0, 1.0), (1.0, 3.0), (2.0, 2.0), (3.0, 3.0)]
def outcomes(df, dir_, a, b):
    """Per row: resolved flag, win flag, R at resolution (target: +b/a, stop: -1), R marked at close for unresolved."""
    up_b, dn_a, dn_b, up_a = (df[f"t_up_{b}"].to_numpy(float), df[f"t_dn_{a}"].to_numpy(float), df[f"t_dn_{b}"].to_numpy(float), df[f"t_up_{a}"].to_numpy(float))
    t_t = np.where(dir_ > 0, up_b, dn_b); t_s = np.where(dir_ > 0, dn_a, up_a)
    resolved = ~(np.isnan(t_t) & np.isnan(t_s)); win = resolved & (np.nan_to_num(t_t, nan=np.inf) < np.nan_to_num(t_s, nan=np.inf))
    r = np.where(win, b / a, np.where(resolved, -1.0, np.nan)); mtm = dir_ * (df["mid_close"].to_numpy(float) - df["mid"].to_numpy(float)) / (a * df["sigma_1m"].to_numpy(float))
    r_all = np.where(resolved, r, mtm); t_res = np.where(resolved, np.fmin(np.nan_to_num(t_t, nan=np.inf), np.nan_to_num(t_s, nan=np.inf)), np.nan)
    return resolved, win, r_all, t_res
def thin(idx, date, be, gap=THIN_S):
    keep, last, lastd = [], -1e9, None
    for i in idx:
        if date[i] != lastd or be[i] - last >= gap: keep.append(i); last, lastd = be[i], date[i]
    return np.array(keep, int)
def score_cell(df, ev_idx, dir_all, a, b, *, seed=SEED, nb=B):
    """ev_idx: thinned event row indices; dir_all: orientation per row (+1/-1, 0 for non-events)."""
    resolved, win, r_all, t_res = outcomes(df, dir_all, a, b)
    n_ev = len(ev_idx); n_res = int(resolved[ev_idx].sum()); wr_ev = float(win[ev_idx].sum() / max(n_res, 1)); exp_ev = float(np.nanmean(r_all[ev_idx])); cens = 1 - n_res / max(n_ev, 1)
    slot = df.slot.to_numpy(); sb = df.sbucket.to_numpy(); usable = df.usable.to_numpy(bool) & (dir_all == 0)
    need = pd.Series(list(zip(slot[ev_idx], sb[ev_idx]))).value_counts().to_dict(); pools = {c: np.flatnonzero(usable & (slot == c[0]) & (sb == c[1])) for c in need}
    short = [c for c, n in need.items() if len(pools[c]) < n]
    up = {}; dn = {}
    for k in (a, b): up[k] = df[f"t_up_{k}"].to_numpy(float); dn[k] = df[f"t_dn_{k}"].to_numpy(float)
    wrs = np.empty(nb); exps = np.empty(nb)
    for j in range(nb):
        rng = np.random.default_rng([seed, j]); picks = np.concatenate([rng.choice(pools[c], size=min(n, len(pools[c])), replace=False) for c, n in need.items()]); d = rng.choice([-1, 1], size=len(picks))
        t_t = np.where(d > 0, up[b][picks], dn[b][picks]); t_s = np.where(d > 0, dn[a][picks], up[a][picks]); res = ~(np.isnan(t_t) & np.isnan(t_s)); w = res & (np.nan_to_num(t_t, nan=np.inf) < np.nan_to_num(t_s, nan=np.inf))
        wrs[j] = w.sum() / max(res.sum(), 1); mtm = d * (df["mid_close"].to_numpy(float)[picks] - df["mid"].to_numpy(float)[picks]) / (a * df["sigma_1m"].to_numpy(float)[picks]); exps[j] = np.nanmean(np.where(w, b / a, np.where(res, -1.0, mtm)))
    base = float(wrs.mean()); lift = wr_ev - base; p = float((1 + np.sum(np.abs(wrs - base) >= abs(lift))) / (nb + 1)); base_exp = float(exps.mean())
    return {"stop": a, "target": b, "n_events": n_ev, "n_resolved": n_res, "censored_share": float(cens), "win_rate": wr_ev, "baseline_win_rate": base, "baseline_sd": float(wrs.std(ddof=1)), "theory": a / (a + b), "lift_pp": lift * 100, "p_two_sided": p,
            "expectancy_R": exp_ev, "baseline_expectancy_R": base_exp, "expectancy_lift_R": exp_ev - base_exp, "median_time_to_resolution_s": float(np.nanmedian(t_res[ev_idx])) if n_res else None, "sign": int(np.sign(lift)), "pools_short": len(short)}
def cell_verdict(a, b):
    if a["sign"] != b["sign"] or a["sign"] == 0: return "FAIL (sign flip)"
    if a["p_two_sided"] <= ALPHA and b["p_two_sided"] <= ALPHA and a["n_resolved"] >= MIN_RESOLVED and b["n_resolved"] >= MIN_RESOLVED: return "PASS DISCOVERY (PRE-COST)"
    return "FAIL"
def confirm_verdict(disc, conf):
    same = np.sign(conf["lift_pp"]) == np.sign(disc["lift_pp"]) and conf["sign"] != 0; comparable = abs(conf["lift_pp"]) >= 0.5 * abs(disc["lift_pp"])
    return ("CONFIRMED (PRE-COST / PENDING)" if same and comparable else ("FAIL confirmation (sign)" if not same else "FAIL confirmation (magnitude < 50% of discovery)"))
