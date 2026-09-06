"""CP2 (run 3) — joint object on ALL discovery bars (guarded loads, stage CP2), F1 thresholds (count only), the
UNCONDITIONAL empirical baseline vs random-walk theory, and the projected confirmation-set power.
No event-conditional outcome is aggregated or printed here."""
import sys, json, time, numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import norm
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); import first_passage as FP
OUT = D3 / "fp_discovery"; OUT.mkdir(exist_ok=True); q = json.loads((D3 / "QUARANTINE.json").read_text()); disc = q["discovery"]; conf = q["confirmation"]
STAGE = "CP2"; Q99 = 0.99; THIN_S = 300; Z = norm.ppf(0.975) + norm.ppf(0.80); PAIRS_SCORED = [(1.0, 1.0), (1.0, 3.0), (2.0, 2.0), (3.0, 3.0)]
def run_engine():
    summaries = []; prev = {i: None for i in ("NIFTY_FUT", "BANKNIFTY_FUT")}; t0 = time.time()
    for d in disc:
        for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
            p = OUT / f"{d}_{inst}.parquet"
            if p.exists() and (OUT / "_summary.json").exists(): pass
            t1 = time.time(); out, s = FP.compute_session(d, inst, STAGE, prev[inst], p); summaries.append(s); prev[inst] = s["this_session_levels"]
            print(f"  {d} {inst:<13} rows={s['rows_in']:>7} snaps={s['snapshots']} bars_mid={s['bars_with_mid']} bars_sigma={s['bars_with_sigma']} med_sigma_1m={s['median_sigma_1m']:.3f} refills b/a={s['refill_events']['bid']}/{s['refill_events']['ask']} prev_levels={'yes' if s['levels']['pdh'] is not None else 'NO'} {time.time()-t1:.0f}s", flush=True)
    (OUT / "_summary.json").write_text(json.dumps(summaries, indent=1)); print(f"  {len(summaries)} discovery sessions in {time.time()-t0:.0f}s", flush=True)
def load(inst):
    fr = []
    for d in disc: f = pd.read_parquet(OUT / f"{d}_{inst}.parquet"); f["date"] = d; fr.append(f)
    return pd.concat(fr, ignore_index=True)
if __name__ == "__main__":
    if "--engine" in sys.argv: run_engine()
    res = {"pairs_scored": PAIRS_SCORED, "z_sum": Z, "thin_s": THIN_S, "instruments": {}}
    for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
        df = load(inst); slot = df.slot.to_numpy(); date = df.date.to_numpy(); sig = df.sigma_1m.to_numpy(float)
        # F1 thresholds: 99th percentile of per-bar refill counts per slot, discovery bars only (count only)
        thr = {}
        for sd in ("bid", "ask"):
            x = df[f"{sd}_refills"].to_numpy(float); thr[sd] = {int(s): float(np.quantile(x[slot == s], Q99)) for s in np.unique(slot)}
        bid_ev = df.bid_refills.to_numpy(float) > df.slot.map(thr["bid"]).to_numpy(float); ask_ev = df.ask_refills.to_numpy(float) > df.slot.map(thr["ask"]).to_numpy(float)
        usable = ~np.isnan(sig) & ~np.isnan(df.censor_s.to_numpy(float)); ev = (bid_ev ^ ask_ev) & usable; both = (bid_ev & ask_ev & usable).sum()
        # sigma quintiles (discovery bars with sigma) for the matched null
        edges = np.nanquantile(sig[usable], [0.2, 0.4, 0.6, 0.8]).tolist(); sbucket = np.digitize(sig, edges)
        # thin events >= THIN_S apart within a session (greedy) — counts only
        idx = np.flatnonzero(ev); keep, last, lastd = [], -1e9, None; be = df.bar_end_s.to_numpy(float)
        for i in idx:
            if date[i] != lastd or be[i] - last >= THIN_S: keep.append(i); last, lastd = be[i], date[i]
        keep = np.array(keep, int); per_sess = pd.Series(date[keep]).value_counts()
        # F2 counts
        f2 = ev & df.near_any.to_numpy(bool); idx2 = np.flatnonzero(f2); keep2, last, lastd = [], -1e9, None
        for i in idx2:
            if date[i] != lastd or be[i] - last >= THIN_S: keep2.append(i); last, lastd = be[i], date[i]
        # UNCONDITIONAL baseline: all usable bars, average of the two orientations (= random orientation in expectation)
        grid = {}
        for a in FP.K:
            for b in FP.K:
                tu_b, td_a, td_b, tu_a = df[f"t_up_{b}"].to_numpy(float), df[f"t_dn_{a}"].to_numpy(float), df[f"t_dn_{b}"].to_numpy(float), df[f"t_up_{a}"].to_numpy(float)
                res_p = usable & ~(np.isnan(tu_b) & np.isnan(td_a)); win_p = res_p & (np.nan_to_num(tu_b, nan=np.inf) < np.nan_to_num(td_a, nan=np.inf))
                res_m = usable & ~(np.isnan(td_b) & np.isnan(tu_a)); win_m = res_m & (np.nan_to_num(td_b, nan=np.inf) < np.nan_to_num(tu_a, nan=np.inf))
                wr = 0.5 * (win_p.sum() / max(res_p.sum(), 1) + win_m.sum() / max(res_m.sum(), 1)); unres = 1 - 0.5 * (res_p.sum() + res_m.sum()) / max(usable.sum(), 1)
                grid[f"{a}:{b}"] = {"stop": a, "target": b, "theory": a / (a + b), "empirical": float(wr), "departure_pp": float((wr - a / (a + b)) * 100), "unresolved_share": float(unres)}
        # censoring at each horizon for the K levels (share of usable bars where NEITHER +k nor -k is reached within H)
        cens = {}
        for hn, hs in FP.HORIZONS.items():
            cens[hn] = {}
            for k in FP.K:
                tu, td = df[f"t_up_{k}"].to_numpy(float), df[f"t_dn_{k}"].to_numpy(float); lim = np.inf if hs is None else hs
                reached = (np.nan_to_num(tu, nan=np.inf) <= lim) | (np.nan_to_num(td, nan=np.inf) <= lim); cens[hn][str(k)] = float(1 - reached[usable].mean())
        # projected confirmation power (confirmation NOT read): events per discovery session x len(conf)
        n_per_sess = len(keep) / len(disc); n_conf_proj = n_per_sess * len(conf); power = {}
        for a, b in PAIRS_SCORED:
            p = grid[f"{a}:{b}"]["empirical"]; mde = Z * np.sqrt(2 * p * (1 - p) / max(n_conf_proj, 1)); n_need = Z ** 2 * 2 * p * (1 - p) / 0.05 ** 2
            power[f"{a}:{b}"] = {"baseline_p": p, "n_conf_projected": n_conf_proj, "mde_pp": mde * 100, "detects_5pp": bool(mde <= 0.05), "n_needed_for_5pp": n_need, "sessions_needed_for_5pp": n_need / max(n_per_sess, 1e-9)}
        res["instruments"][inst] = {"sessions": len(disc), "bars": int(len(df)), "usable_bars": int(usable.sum()), "thresholds": thr, "sigma_quintile_edges": edges, "F1": {"raw": int(ev.sum()), "both_sides_dropped": int(both), "thinned": int(len(keep)), "per_session_min_med_max": [int(per_sess.min()), float(per_sess.median()), int(per_sess.max())], "sessions_with_events": int(len(per_sess)), "per_session_rate": n_per_sess}, "F2": {"raw": int(f2.sum()), "thinned": int(len(keep2))}, "baseline_grid": grid, "censoring": cens, "power_confirmation_projected": power}
        print(f"\n  {inst}: discovery bars={len(df)} usable(sigma+path)={usable.sum()} | F1 raw={ev.sum()} (both-sides dropped {both}) thinned>={THIN_S}s: {len(keep)} in {len(per_sess)} sessions, per-session min/med/max {per_sess.min()}/{per_sess.median():.0f}/{per_sess.max()} | F2 raw={f2.sum()} thinned={len(keep2)}")
        print(f"    sigma_1m quintile edges (pts): {[round(e, 3) for e in edges]}")
        print("    unconditional baseline vs random-walk theory (win% = P(target before stop), resolved bars; unresolved share):")
        for a, b in PAIRS_SCORED + [(1.0, 2.0), (0.5, 1.5), (0.25, 0.25), (3.0, 1.0)]: g = grid[f"{a}:{b}"]; print(f"      stop {a}σ target {b}σ: theory {g['theory']*100:5.1f}%  empirical {g['empirical']*100:5.1f}%  departure {g['departure_pp']:+5.1f} pp  unresolved {g['unresolved_share']*100:4.1f}%")
        print("    censoring (neither ±kσ reached within H), share of usable bars: " + " | ".join(f"{hn}: k=1 {cens[hn]['1.0']*100:.0f}% k=3 {cens[hn]['3.0']*100:.0f}%" for hn in FP.HORIZONS))
        for pr, pw in power.items(): print(f"    power (confirmation PROJECTED n = {pw['n_conf_projected']:.0f} = {n_per_sess:.1f}/session x {len(conf)}): pair {pr}: MDE {pw['mde_pp']:.1f} pp (p0={pw['baseline_p']:.3f}) -> {'detects 5 pp' if pw['detects_5pp'] else 'UNPOWERED-CONFIRM'}; 5 pp needs n={pw['n_needed_for_5pp']:.0f} = {pw['sessions_needed_for_5pp']:.0f} sessions")
    (D3 / "cp2_baseline.json").write_text(json.dumps(res, indent=1)); print("\n  written cp2_baseline.json")
