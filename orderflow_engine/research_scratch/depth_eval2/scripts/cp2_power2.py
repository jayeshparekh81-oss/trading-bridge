"""CP2 (run 2) — POWER CHECK. Counts events at the stated triggers; NO event-conditional forward return. Unconditional
sigma_h / median|move|_h over all bars are the only outcome-related quantities (needed for the MDE arithmetic).
Triggers (per instrument, per 15-min slot pooled over usable sessions):
  SIGNED state features: center = slot median; dev = f - center; event iff |dev| > q99(|dev| in slot); orientation = sign(dev)
  COUNT features (trailing 10-bar sums): event iff value > q99(slot) and value > 0 (strict, ties keep the rate <= 1%)"""
import json, numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import norm
D2 = Path(__file__).resolve().parent.parent; FEAT = D2 / "features"
SIGNED = ["deep_imb_qty", "deep_imb_orders", "slope_diff", "conc_diff"]
COUNTS = [f"{k}_{s}_w" for k in ("wall_appear", "wall_disappear", "deep_refill") for s in ("bid", "ask")]
HB = {"5s": 1, "30s": 6, "120s": 24}; Q = 0.99; Z = norm.ppf(0.975) + norm.ppf(0.80); RUN1_BPS_30S = 0.5
def load(inst):
    frames = []
    for p in sorted(FEAT.glob(f"*_{inst}.parquet")): f = pd.read_parquet(p); f["date"] = p.name[:10]; frames.append(f)
    return pd.concat(frames, ignore_index=True)
def events_signed(df, feat, thr=None):
    x = df[feat].to_numpy(float); slot = df.slot.to_numpy(); ev = np.zeros(len(df), bool); orient = np.zeros(len(df), np.int8); thr = {} if thr is None else thr; learn = not thr
    for s in np.unique(slot):
        m = (slot == s) & ~np.isnan(x)
        if not m.any(): continue
        if learn: c = float(np.median(x[m])); q = float(np.quantile(np.abs(x[m] - c), Q)); thr[int(s)] = {"center": c, "q99_absdev": q}
        c, q = thr[int(s)]["center"], thr[int(s)]["q99_absdev"]; dev = x - c; hit = m & (np.abs(dev) > q); ev |= hit; orient[hit] = np.sign(dev[hit])
    return ev, orient, thr
def events_count(df, feat, thr=None):
    x = df[feat].to_numpy(float); slot = df.slot.to_numpy(); ev = np.zeros(len(df), bool); thr = {} if thr is None else thr; learn = not thr
    for s in np.unique(slot):
        m = (slot == s) & ~np.isnan(x)
        if not m.any(): continue
        if learn: thr[int(s)] = float(np.quantile(x[m], Q))
        ev |= m & (x > thr[int(s)]) & (x > 0)
    return ev, thr
def thin(idx, date, hb):
    keep, last, lastd = [], -10**9, None
    for i in idx:
        if date[i] != lastd or i - last >= hb: keep.append(i); last, lastd = i, date[i]
    return np.array(keep, dtype=int)
if __name__ == "__main__":
    res = {"trigger_quantile": Q, "z_sum": Z, "instruments": {}}
    print(f"  MDE = {Z:.5f} * sigma_h * sqrt(2/n_eff); n_eff = events thinned to >= h apart within a session (close: sessions with >= 1 event); run-1 reference {RUN1_BPS_30S} bp at 30 s")
    for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
        df = load(inst); mid = df.mid.to_numpy(float); date = df.date.to_numpy(); n_sess = df.date.nunique(); mm = float(np.nanmean(mid))
        fwd = {}
        for h, hb in HB.items(): v = np.full(len(df), np.nan); same = date[hb:] == date[:-hb]; v[:-hb] = np.where(same, mid[hb:] - mid[:-hb], np.nan); fwd[h] = v
        close = df.groupby("date").mid.transform(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan).to_numpy(float); fwd["close"] = close - mid
        disp = {h: {"sigma_pts": float(np.nanstd(v)), "median_abs_pts": float(np.nanmedian(np.abs(v))), "n_bars": int(np.sum(~np.isnan(v)))} for h, v in fwd.items()}
        print(f"\n  {inst}: sessions={n_sess} bars={len(df)} mean_mid={mm:.2f}")
        for h in fwd: print(f"    unconditional {h:>5}: sigma={disp[h]['sigma_pts']:.3f} pts ({disp[h]['sigma_pts']/mm*1e4:.2f} bps) median|move|={disp[h]['median_abs_pts']:.3f} pts n_bars={disp[h]['n_bars']}")
        R = {"sessions": int(n_sess), "bars": int(len(df)), "mean_mid": mm, "dispersion": disp, "features": {}}
        for feat in SIGNED + COUNTS:
            if feat in SIGNED: ev, orient, thr = events_signed(df, feat); kind = "signed"
            else: ev, thr = events_count(df, feat); kind = "count"
            x = df[feat].to_numpy(float); defined = int(np.sum(~np.isnan(x))); idx = np.flatnonzero(ev); n_raw = int(len(idx))
            # independent recount: pandas groupby
            if feat in SIGNED:
                g = df.groupby("slot")[feat]; c = g.transform("median"); ad = (df[feat] - c).abs(); q = ad.groupby(df.slot).transform(lambda s: s.quantile(Q)); n2 = int((ad > q).sum())
            else:
                q = df.groupby("slot")[feat].transform(lambda s: s.quantile(Q)); n2 = int(((df[feat] > q) & (df[feat] > 0)).sum())
            n_ep = int(1 + np.sum((np.diff(idx) != 1) | (date[idx[1:]] != date[idx[:-1]]))) if n_raw else 0
            per = pd.Series(date[idx]).value_counts() if n_raw else pd.Series(dtype=int); n_eff = {h: int(len(thin(idx, date, hb))) for h, hb in HB.items()}; n_eff["close"] = int(len(per))
            rows = {}
            for h in fwd:
                mde = Z * disp[h]["sigma_pts"] * np.sqrt(2.0 / n_eff[h]) if n_eff[h] > 0 else float("inf")
                rows[h] = {"n_eff": n_eff[h], "mde_pts": float(mde), "mde_bps": float(mde / mm * 1e4), "median_abs_move_pts": disp[h]["median_abs_pts"], "powered": bool(mde <= disp[h]["median_abs_pts"]), "detects_run1_0p5bp": bool(mde / mm * 1e4 <= RUN1_BPS_30S) if h == "30s" else None}
            spread = {"sessions_with_events": int(len(per)), "min": int(per.min()) if n_raw else 0, "median": float(per.median()) if n_raw else 0, "max": int(per.max()) if n_raw else 0, "top_session_share": float(per.max() / n_raw) if n_raw else 0}
            R["features"][feat] = {"kind": kind, "defined_bars": defined, "n_raw": n_raw, "n_raw_independent_recount": n2, "event_rate_of_defined": n_raw / defined if defined else 0, "n_episodes": n_ep, "thresholds_by_slot": thr, "per_session_spread": spread, "by_horizon": rows}
            print(f"    {feat:<22} {kind:<6} defined={defined:>6} n_raw={n_raw:>5} (recount {n2}) rate={n_raw/defined*100 if defined else 0:.2f}% episodes={n_ep} per-session min/med/max={spread['min']}/{spread['median']:.0f}/{spread['max']} top-share={spread['top_session_share']:.2f} sessions={spread['sessions_with_events']}")
            for h, r in rows.items(): print(f"        {h:>5}: n_eff={r['n_eff']:>5} MDE={r['mde_pts']:.3f} pts = {r['mde_bps']:.3f} bps | median|move|={r['median_abs_move_pts']:.3f} -> {'POWERED' if r['powered'] else 'UNPOWERED'}" + (f" | detects 0.5 bp: {'YES' if r['detects_run1_0p5bp'] else 'NO'}" if h == "30s" else ""))
        res["instruments"][inst] = R
    (D2 / "cp2_power2.json").write_text(json.dumps(res, indent=1)); print("\n  written cp2_power2.json")
