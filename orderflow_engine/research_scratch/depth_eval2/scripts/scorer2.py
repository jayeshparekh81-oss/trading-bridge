"""scorer2.py — scores one (instrument, feature, horizon) cell per PREREG2.md. Run-1 harness fixes kept: per-draw seed
sequences [seed, b] (no overlap between seeds), deterministic pickers, clean injection on random events."""
import json, sys, numpy as np, pandas as pd
from pathlib import Path
D2 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D2 / "scripts")); import cp2_power2 as C
PW = json.loads((D2 / "cp2_power2.json").read_text()); B = 2000; SEED = 20260906; N_HYP_BOTH_RUNS = 46; ALPHA = 0.05 / N_HYP_BOTH_RUNS; MIN_NEFF = 100
HB = C.HB
def powered_cells():
    out = {}
    for h in ("5s", "30s", "120s"):
        out[h] = [f for f in C.SIGNED + C.COUNTS if all(PW["instruments"][i]["features"][f]["by_horizon"][h]["powered"] for i in ("NIFTY_FUT", "BANKNIFTY_FUT"))]
    return out
def load(inst):
    df = C.load(inst); mid = df.mid.to_numpy(float); date = df.date.to_numpy()
    for h, hb in HB.items(): v = np.full(len(df), np.nan); same = date[hb:] == date[:-hb]; v[:-hb] = np.where(same, mid[hb:] - mid[:-hb], np.nan); df[f"R_{h}"] = v
    close = df.groupby("date").mid.transform(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan).to_numpy(float); df["R_close"] = close - mid
    return df
def events_for(df, inst, feat):
    thr = PW["instruments"][inst]["features"][feat]["thresholds_by_slot"]; thr = {int(k): v for k, v in thr.items()}
    if feat in C.SIGNED: ev, orient, _ = C.events_signed(df, feat, thr); return ev, orient
    ev, _ = C.events_count(df, feat, thr); return ev, None
def orientation_all(df, inst, feat):
    """sign(dev) for EVERY bar (signed features) so baseline bars are oriented by their own deviation; None for counts."""
    if feat not in C.SIGNED: return None
    thr = {int(k): v for k, v in PW["instruments"][inst]["features"][feat]["thresholds_by_slot"].items()}
    x = df[feat].to_numpy(float); slot = df.slot.to_numpy(); o = np.zeros(len(df), np.int8)
    for s, t in thr.items(): m = slot == s; o[m] = np.sign(x[m] - t["center"])
    return o
def score(df, inst, feat, h, *, ev=None, inject=0.0, seed=SEED):
    ev0, _ = events_for(df, inst, feat); ev = ev0 if ev is None else ev
    orient = orientation_all(df, inst, feat)
    R = df[f"R_{h}"].to_numpy(float).copy(); slot = df.slot.to_numpy(); date = df.date.to_numpy()
    idx_all = np.flatnonzero(ev & ~np.isnan(R))
    if inject:
        R[idx_all] += inject * (orient[idx_all] if orient is not None else 1)      # oriented injection: shifts the oriented mean by +inject
    Y = R * orient if orient is not None else R                                       # oriented outcome for signed features
    hb = HB.get(h); kept = C.thin(idx_all, date, hb) if h != "close" else idx_all
    if len(kept) == 0: return {"inst": inst, "feature": feat, "horizon": h, "n_raw": int(len(idx_all)), "n_eff": 0, "note": "no events with defined return"}
    if orient is not None: kept = kept[orient[kept] != 0]
    nonev = ~ev & ~np.isnan(R); need = pd.Series(slot[kept]).value_counts().to_dict(); pools = {s: np.flatnonzero(nonev & (slot == s)) for s in need}
    means = np.empty(B)
    for b in range(B):
        rng = np.random.default_rng([seed, b]); picks = np.concatenate([rng.choice(pools[s], size=n, replace=False) for s, n in need.items()]); means[b] = Y[picks].mean()
    base = float(means.mean()); mean_ev = float(Y[kept].mean()); diff = mean_ev - base
    p = float((1 + np.sum(np.abs(means - base) >= abs(diff))) / (B + 1)); mm = PW["instruments"][inst]["mean_mid"]
    return {"inst": inst, "feature": feat, "horizon": h, "n_raw": int(len(idx_all)), "n_eff": int(len(kept)), "mean_event_pts": mean_ev, "baseline_mean_pts": base, "diff_pts": float(diff), "diff_bps": float(diff / mm * 1e4),
            "sd_event_pts": float(Y[kept].std(ddof=1)) if len(kept) > 1 else float("nan"), "sd_nonevent_pts": float(Y[nonev].std(ddof=1)), "sd_of_baseline_means_pts": float(means.std(ddof=1)), "p_two_sided": p, "sign": int(np.sign(diff)), "oriented": orient is not None}
def cell_verdict(a, b):
    if "note" in a or "note" in b: return "NOT SCORED"
    if not (a["sign"] == b["sign"] and a["sign"] != 0): return "FAIL (sign flip)"
    if a["p_two_sided"] <= ALPHA and b["p_two_sided"] <= ALPHA and a["n_eff"] >= MIN_NEFF and b["n_eff"] >= MIN_NEFF: return "PRE-COST PASS / PENDING"
    return "FAIL"
