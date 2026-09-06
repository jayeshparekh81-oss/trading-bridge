"""CP1 self-check — one full DISCOVERY session by an INDEPENDENT path: (a) mid series via pandas merge_asof, (b) sigma via
pandas rolling std, (c) first-passage times / MFE / MAE by a naive forward scan (np.where on the raw path) on a random
subset of 300 bars, (d) refill counts vs run 1's independently produced feature parquet for the same session."""
import sys, json, numpy as np, pandas as pd
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); import first_passage as FP, qguard
date, inst = sys.argv[1], sys.argv[2]; stage = "CP1"
ref, summ = FP.compute_session(date, inst, stage, None)
df = qguard.load_session(date, inst, stage, FP.COLS); ts = df.ts_recv_ns.to_numpy(np.int64)
ends = FP.grid_ns(date)
# (a) mid series via merge_asof
b = df[df.side == 0][["ts_recv_ns", "price_1"]].rename(columns={"price_1": "b1", "ts_recv_ns": "bts"}); a = df[df.side == 1][["ts_recv_ns", "price_1"]].rename(columns={"price_1": "a1", "ts_recv_ns": "ats"})
u = pd.DataFrame({"ts_recv_ns": np.unique(ts)}); m = pd.merge_asof(u, b, left_on="ts_recv_ns", right_on="bts", direction="backward"); m = pd.merge_asof(m, a, left_on="ts_recv_ns", right_on="ats", direction="backward")
ok = (m.ts_recv_ns - m.bts <= FP.MID_MAX_AGE_NS) & (m.ts_recv_ns - m.ats <= FP.MID_MAX_AGE_NS) & (m.b1 > 0) & (m.a1 > 0); mid_alt = np.where(ok, (m.b1 + m.a1) / 2, np.nan).astype(float)
u_mod, mid_mod = FP.mid_series(ts, df.side.to_numpy(), df.price_1.to_numpy(float))
same_mid = np.allclose(np.nan_to_num(mid_mod, nan=-1), np.nan_to_num(mid_alt, nan=-1)); print(f"  mid series ({len(u_mod)} snapshots): independent merge_asof path {'MATCHES' if same_mid else 'DIFFERS'}")
bm = pd.merge_asof(pd.DataFrame({"ts_recv_ns": ends}), pd.DataFrame({"ts_recv_ns": u_mod, "mid": mid_alt}), on="ts_recv_ns", direction="backward"); bm_ts = pd.merge_asof(pd.DataFrame({"ts_recv_ns": ends}), pd.DataFrame({"ts_recv_ns": u_mod, "uts": u_mod}), on="ts_recv_ns", direction="backward")
bar_mid_alt = np.where(ends - bm_ts.uts.to_numpy() <= FP.MID_MAX_AGE_NS, bm.mid.to_numpy(), np.nan)
print(f"  bar mid: {'MATCHES' if np.allclose(np.nan_to_num(ref.mid.to_numpy(), nan=-1), np.nan_to_num(bar_mid_alt, nan=-1)) else 'DIFFERS'}")
# (b) sigma via pandas rolling (window of changes ending at the previous bar)
d = pd.Series(bar_mid_alt).diff(); sig_alt = (d.shift(1).rolling(FP.SIGMA_WIN, min_periods=FP.SIGMA_MIN).std(ddof=1) * FP.SIGMA_SCALE).to_numpy()
sr = ref.sigma_1m.to_numpy(); both = ~np.isnan(sr) & ~np.isnan(sig_alt); print(f"  sigma_1m: defined module {np.sum(~np.isnan(sr))} vs pandas {np.sum(~np.isnan(sig_alt))}; max |diff| on common bars {np.max(np.abs(sr[both]-sig_alt[both])):.3e} -> {'MATCHES' if np.allclose(sr[both], sig_alt[both], rtol=1e-9, atol=1e-9) and np.sum(~np.isnan(sr)) == np.sum(~np.isnan(sig_alt)) else 'DIFFERS'}")
# (c) naive first passage on 300 random bars
rng = np.random.default_rng(3); valid = np.flatnonzero(~np.isnan(ref.censor_s.to_numpy())); pick = rng.choice(valid, size=min(300, len(valid)), replace=False)
ts_s = (u_mod - ends[0]) / 1e9; vm = ~np.isnan(mid_mod); ts_v, mid_v = ts_s[vm], mid_mod[vm]; be = (ends - ends[0]) / 1e9; mism = 0; checked = 0
for i in pick:
    j0 = np.searchsorted(ts_v, be[i], side="right"); path = mid_v[j0:] - ref.mid.iloc[i]; rt = ts_v[j0:] - be[i]; s = ref.sigma_1m.iloc[i]
    for k in FP.K:
        w = np.flatnonzero(path >= k * s); t_up = rt[w[0]] if len(w) else np.nan; w2 = np.flatnonzero(path <= -k * s); t_dn = rt[w2[0]] if len(w2) else np.nan
        for got, exp in ((ref[f"t_up_{k}"].iloc[i], t_up), (ref[f"t_dn_{k}"].iloc[i], t_dn)):
            checked += 1
            if not ((np.isnan(got) and np.isnan(exp)) or (not np.isnan(got) and not np.isnan(exp) and abs(got - exp) < 1e-3)): mism += 1
    for hn, hs in FP.HORIZONS.items():
        mm = len(path) if hs is None else int(np.sum(rt <= hs))
        if mm == 0: continue
        checked += 2; seg = path[:mm]
        if abs(ref[f"mfe_{hn}"].iloc[i] - max(seg.max(), 0)) > 1e-3: mism += 1
        if abs(ref[f"mae_{hn}"].iloc[i] - min(seg.min(), 0)) > 1e-3: mism += 1
print(f"  first-passage / MFE / MAE naive scan on {len(pick)} bars: {checked} values checked, {mism} mismatches -> {'MATCHES' if mism == 0 else 'DIFFERS'}")
# (d) refill counts vs run 1's stored features (independent execution + binning)
r1 = Path(D3.parent / "depth_eval" / "features" / f"{date}_{inst}.parquet")
if r1.exists():
    f1 = pd.read_parquet(r1); same = (f1.bid_refills.to_numpy() == ref.bid_refills.to_numpy()).all() and (f1.ask_refills.to_numpy() == ref.ask_refills.to_numpy()).all()
    print(f"  refill counts vs run-1 stored parquet: {'IDENTICAL' if same else 'DIFFER'} (bid {ref.bid_refills.sum()} / ask {ref.ask_refills.sum()})")
else: print("  refill counts: run-1 parquet not present for this session -> NOT CROSS-CHECKED")
print(f"  summary: {json.dumps({k: v for k, v in summ.items() if k in ('rows_in','snapshots','bars_with_mid','bars_with_sigma','median_sigma_1m','refill_events')})}")
