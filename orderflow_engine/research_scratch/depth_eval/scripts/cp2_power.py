"""CP2 — POWER CHECK. Counts events at the stated trigger. Computes NO event-conditional forward return.
The only outcome-related quantities here are UNCONDITIONAL (all bars, no feature joined): the std and
median |.| of forward mid changes per horizon, needed for the MDE arithmetic and its plausibility anchor."""
import json, numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import norm
DE = Path(__file__).resolve().parent.parent; FEAT = DE / "features"
EXCLUDE = {"2026-08-17"}                      # CP1: book crossed/locked at bar end on ~all bars (see CP1_inventory.md)
FEATURES = ["bid_refills", "ask_refills", "bid_refill_ratio", "ask_refill_ratio", "bid_refills_w", "ask_refills_w"]
HB = {"5s": 1, "30s": 6, "120s": 24}; Q = 0.99; Z = norm.ppf(0.975) + norm.ppf(0.80)
print(f"  trigger: per instrument, per 15-min slot pooled over sessions, T = quantile {Q} of the feature's own values (ratio: defined values only); event iff value > T")
print(f"  MDE = (z0.975 + z0.80) * sigma_h * sqrt(2/n_eff) = {Z:.5f} * sigma_h * sqrt(2/n_eff); n_eff = events thinned to >= h apart within a session (close: sessions with >= 1 event)")
print(f"  excluded sessions: {sorted(EXCLUDE)}")
res = {"trigger_quantile": Q, "z_sum": Z, "excluded": sorted(EXCLUDE), "instruments": {}}
for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
    frames = []
    for p in sorted(FEAT.glob(f"*_{inst}.parquet")):
        if p.name[:10] in EXCLUDE: continue
        f = pd.read_parquet(p); f["date"] = p.name[:10]; frames.append(f)
    df = pd.concat(frames, ignore_index=True); mid = df.mid.to_numpy(float); date = df.date.to_numpy(); slot = df.slot.to_numpy()
    n_sess = df.date.nunique(); mean_mid = float(np.nanmean(mid))
    fwd = {}
    for h, hb in HB.items():
        v = np.full(len(df), np.nan); same = date[hb:] == date[:-hb]; v[:-hb] = np.where(same, mid[hb:] - mid[:-hb], np.nan); fwd[h] = v
    close = df.groupby("date").mid.transform(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan).to_numpy(float); fwd["close"] = close - mid
    disp = {h: {"sigma_pts": float(np.nanstd(v)), "median_abs_pts": float(np.nanmedian(np.abs(v))), "n_bars": int(np.sum(~np.isnan(v)))} for h, v in fwd.items()}
    nz = np.abs(fwd["5s"]); tick = float(np.nanmin(nz[nz > 0]))
    print(f"\n  {inst}: sessions={n_sess} bars={len(df)} mean_mid={mean_mid:.2f} min positive |dmid_5s|={tick} (tick check)")
    for h in fwd: print(f"    unconditional {h:>5}: sigma={disp[h]['sigma_pts']:.3f} pts ({disp[h]['sigma_pts']/mean_mid*1e4:.2f} bps)  median|move|={disp[h]['median_abs_pts']:.3f} pts  n_bars={disp[h]['n_bars']}")
    res["instruments"][inst] = {"sessions": int(n_sess), "bars": int(len(df)), "mean_mid": mean_mid, "tick_check": tick, "dispersion": disp, "features": {}}
    for feat in FEATURES:
        x = df[feat].to_numpy(float); ev = np.zeros(len(df), bool); thr = {}
        for s in np.unique(slot):
            m = (slot == s) & ~np.isnan(x)
            if not m.any(): continue
            thr[int(s)] = float(np.quantile(x[m], Q)); ev |= m & (x > thr[int(s)])
        idx = np.flatnonzero(ev); n_raw = int(len(idx)); defined = int(np.sum(~np.isnan(x)))
        n_ep = int(1 + np.sum((np.diff(idx) != 1) | (date[idx[1:]] != date[idx[:-1]]))) if n_raw else 0
        n_eff = {}
        for h, hb in HB.items():
            keep, last, lastd = 0, -10**9, None
            for i in idx:
                if date[i] != lastd or i - last >= hb: keep += 1; last, lastd = i, date[i]
            n_eff[h] = keep
        per_sess = pd.Series(date[idx]).value_counts() if n_raw else pd.Series(dtype=int)
        n_eff["close"] = int(len(per_sess))
        # independent recount: pandas groupby quantile + map
        t2 = df.groupby("slot")[feat].quantile(Q); n_raw2 = int((df[feat] > df.slot.map(t2)).sum())
        rows = {}
        for h in fwd:
            mde = Z * disp[h]["sigma_pts"] * np.sqrt(2.0 / n_eff[h]) if n_eff[h] > 0 else float("inf")
            rows[h] = {"n_eff": int(n_eff[h]), "mde_pts": float(mde), "mde_bps": float(mde / mean_mid * 1e4), "median_abs_move_pts": disp[h]["median_abs_pts"], "powered": bool(mde <= disp[h]["median_abs_pts"])}
        spread = {"sessions_with_events": int(len(per_sess)), "min": int(per_sess.min()) if n_raw else 0, "median": float(per_sess.median()) if n_raw else 0, "max": int(per_sess.max()) if n_raw else 0, "top_session_share": float(per_sess.max() / n_raw) if n_raw else 0}
        res["instruments"][inst]["features"][feat] = {"defined_bars": defined, "n_raw": n_raw, "n_raw_independent_recount": n_raw2, "event_rate_of_defined": n_raw / defined if defined else 0, "n_episodes": n_ep, "thresholds_by_slot": thr, "per_session_spread": spread, "by_horizon": rows}
        print(f"    {feat:<17} defined={defined:>6} events n_raw={n_raw:>5} (recount {n_raw2}, rate {n_raw/defined*100 if defined else 0:.2f}%) episodes={n_ep} per-session min/med/max={spread['min']}/{spread['median']:.0f}/{spread['max']} top-share={spread['top_session_share']:.2f} sessions={spread['sessions_with_events']}")
        for h, r in rows.items(): print(f"        {h:>5}: n_eff={r['n_eff']:>5} MDE={r['mde_pts']:.3f} pts = {r['mde_bps']:.2f} bps | median|move|={r['median_abs_move_pts']:.3f} pts -> {'POWERED' if r['powered'] else 'UNPOWERED'}")
(DE / "cp2_power.json").write_text(json.dumps(res, indent=1)); print("\n  written cp2_power.json")
