"""CP1 self-check — recompute ONE full session with an INDEPENDENT code path (pandas/polyfit state features; array-based
event loop with np.isin) and diff against deep_book.compute_session. Usage: python3 cp1_selfcheck.py DATE INST KEY"""
import sys, numpy as np, pandas as pd
from pathlib import Path
D2 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D2)); import deep_book as DB
date, inst, key = sys.argv[1], sys.argv[2], sys.argv[3]
ref, _ = DB.compute_session(date, inst, key)
df = DB.load_session(key); ts = df.ts_recv_ns.to_numpy(np.int64); side = df.side.to_numpy()
P = df[DB.PCOLS].to_numpy(float); Q = df[DB.QCOLS].to_numpy(float); O = df[DB.OCOLS].to_numpy(float)
# --- independent state features: pandas masks + per-row np.polyfit ---
v = (P > 0) & (Q > 0); Qm = pd.DataFrame(np.where(v, Q, 0.0)); Om = pd.DataFrame(np.where(v & (O > 0), O, 0.0))
deep_q = Qm.iloc[:, 5:].sum(axis=1).to_numpy(); tot_q = Qm.sum(axis=1).to_numpy(); deep_o = Om.iloc[:, 5:].sum(axis=1).to_numpy()
conc = np.where(tot_q > 0, deep_q / np.where(tot_q > 0, tot_q, 1), np.nan)
slope = np.full(len(df), np.nan); x = np.arange(1, 21, dtype=float)
for k in range(len(df)):
    m = v[k]
    if m.sum() >= 3: slope[k] = np.polyfit(x[m], np.log(Q[k, m]), 1)[0]
ends = DB.grid(date); comp = {}
for lab, sv in (("bid", DB.SIDE_BID), ("ask", DB.SIDE_ASK)):
    m = side == sv; sub = pd.DataFrame({"ts": ts[m], "p1": P[m, 0], "deep_q": deep_q[m], "deep_o": deep_o[m], "conc": conc[m], "slope": slope[m]})
    a = pd.merge_asof(pd.DataFrame({"ts": ends}), sub, on="ts", direction="backward"); ok = (ends - a.ts.to_numpy() <= DB.MID_MAX_AGE_NS) & (a.p1.to_numpy() > 0) if False else None
    tsm = ts[m]; i = np.searchsorted(tsm, ends, side="right") - 1; ok = (i >= 0) & (ends - tsm[np.clip(i, 0, None)] <= DB.MID_MAX_AGE_NS) & (P[m, 0][np.clip(i, 0, None)] > 0)
    for name, arr in (("deep_q", deep_q), ("deep_o", deep_o), ("conc", conc), ("slope", slope)): comp[f"{name}_{lab}"] = np.where(ok, arr[m][np.clip(i, 0, None)], np.nan)
imb_q = (comp["deep_q_bid"] - comp["deep_q_ask"]) / (comp["deep_q_bid"] + comp["deep_q_ask"]); imb_o = (comp["deep_o_bid"] - comp["deep_o_ask"]) / (comp["deep_o_bid"] + comp["deep_o_ask"])
checks = {"deep_imb_qty": imb_q, "deep_imb_orders": imb_o, "slope_diff": comp["slope_bid"] - comp["slope_ask"], "conc_diff": comp["conc_bid"] - comp["conc_ask"]}
for name, arr in checks.items():
    r = ref[name].to_numpy(float); same = np.allclose(np.nan_to_num(r, nan=-9e9), np.nan_to_num(arr, nan=-9e9), rtol=1e-9, atol=1e-9)
    print(f"  state {name:<16}: independent path {'MATCHES' if same else 'DIFFERS'} (max |diff| {np.nanmax(np.abs(r - arr)):.2e})")
# --- independent event path: per side, arrays + np.isin; same definitions (k=5, P90 of last 500 deep sizes refreshed every 25 snapshots, gap 5 s) ---
events = []
for lab, sv in (("bid", DB.SIDE_BID), ("ask", DB.SIDE_ASK)):
    rows = np.flatnonzero(side == sv); prev = None; pend = {}; sizes = []; p90 = None; n = 0
    for k in rows:
        vk = (P[k] > 0) & (Q[k] > 0); pr, qt, lv = P[k][vk], Q[k][vk], (np.arange(20) + 1)[vk]
        sizes += qt[lv > 5].tolist(); sizes = sizes[-500:]; n += 1
        if n % 25 == 0 and len(sizes) >= 50: p90 = float(np.percentile(sizes, 90))
        cur = (int(ts[k]), pr, qt, lv); pv = prev; prev = cur
        if pv is None: continue
        if cur[0] - pv[0] > DB.GAP_GUARD_NS: pend = {}; continue
        if len(pr) == 0 or len(pv[1]) == 0: continue
        ppr, pqt, plv = pv[1], pv[2], pv[3]
        both = np.isin(pr, ppr)
        for price, q1, l1 in zip(pr[both], qt[both], lv[both]):
            j = np.flatnonzero(ppr == price)[0]; q0, l0 = pqt[j], plv[j]
            if l0 <= 5 or l1 <= 5: continue
            d = q0 - q1
            if d > 0: pend.setdefault(float(price), []).append([d, 5])
            elif d < 0 and pend.get(float(price)): events.append((cur[0], lab, "deep_refill", float(price), pend[float(price)].pop(0)[0], -d))
        if p90 is not None:
            lo_c, hi_c, lo_p, hi_p = pr.min(), pr.max(), ppr.min(), ppr.max()
            for price, q, l in zip(pr[~both], qt[~both], lv[~both]):
                if l > 5 and q >= p90 and lo_p < price < hi_p: events.append((cur[0], lab, "wall_appear", float(price), 0.0, float(q)))
            gone = ~np.isin(ppr, pr)
            for price, q, l in zip(ppr[gone], pqt[gone], plv[gone]):
                if l > 5 and q >= p90 and lo_c < price < hi_c: events.append((cur[0], lab, "wall_disappear", float(price), float(q), 0.0))
        for price in list(pend):
            lst = [x for x in pend[price] if (x.__setitem__(1, x[1] - 1) or x[1] > 0)]
            if lst: pend[price] = lst
            else: del pend[price]
ref_ev = DB.deep_events(ts, side, P, Q)
key_ = lambda e: (e[0], e[1], e[2], round(e[3], 4)); a = sorted(key_(e) for e in ref_ev); b = sorted(key_(e) for e in events)
print(f"  events: module {len(a)} vs independent {len(b)} -> {'IDENTICAL' if a == b else 'DIFFER'}")
for kind in ("deep_refill", "wall_appear", "wall_disappear"):
    for lab in ("bid", "ask"): print(f"    {kind:<15} {lab}: module {sum(1 for e in a if e[1]==lab and e[2]==kind)} independent {sum(1 for e in b if e[1]==lab and e[2]==kind)}")
