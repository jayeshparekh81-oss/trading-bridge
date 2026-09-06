"""scorer.py — scores one (instrument, feature, horizon) cell EXACTLY per PREREG.md §2–§7. Reused by CP5 (calibration)
and CP6 (the one real run). Nothing here reads the trade tape."""
import json, numpy as np, pandas as pd
from pathlib import Path
DE = Path(__file__).resolve().parent.parent; FEAT = DE / "features"
PW = json.loads((DE / "cp2_power.json").read_text()); EXCLUDE = set(PW["excluded"])
HB = {"5s": 1, "30s": 6, "120s": 24}; B = 1000; SEED = 20260905; ALPHA = 0.05 / 16; MIN_NEFF = 100
POWERED = {"5s": ["bid_refills", "ask_refills", "bid_refills_w", "ask_refills_w"],
           "30s": ["bid_refills", "ask_refills", "bid_refill_ratio", "ask_refill_ratio", "bid_refills_w", "ask_refills_w"],
           "120s": ["bid_refills", "ask_refills", "bid_refill_ratio", "ask_refill_ratio", "bid_refills_w", "ask_refills_w"]}
ALL_FEATURES = POWERED["30s"]

def load(inst):
    frames = []
    for p in sorted(FEAT.glob(f"*_{inst}.parquet")):
        if p.name[:10] in EXCLUDE: continue
        f = pd.read_parquet(p); f["date"] = p.name[:10]; frames.append(f)
    df = pd.concat(frames, ignore_index=True); mid = df.mid.to_numpy(float); date = df.date.to_numpy()
    for h, hb in HB.items():                                       # forward mid change, same session only (PREREG §2-3)
        v = np.full(len(df), np.nan); same = date[hb:] == date[:-hb]; v[:-hb] = np.where(same, mid[hb:] - mid[:-hb], np.nan); df[f"R_{h}"] = v
    close = df.groupby("date").mid.transform(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan).to_numpy(float); df["R_close"] = close - mid
    return df

def events_for(df, inst, feat):
    thr = {int(k): v for k, v in PW["instruments"][inst]["features"][feat]["thresholds_by_slot"].items()}   # frozen (PREREG §4)
    x = df[feat].to_numpy(float); T = df.slot.map(thr).to_numpy(float)
    return ~np.isnan(x) & (x > T)

def thin(idx, date, hb):
    keep, last, lastd = [], -10**9, None
    for i in idx:
        if date[i] != lastd or i - last >= hb: keep.append(i); last, lastd = i, date[i]
    return np.array(keep, dtype=int)

def score(df, inst, feat, h, *, ev=None, inject=0.0, seed=SEED):
    """PREREG §5: thinned events (n_eff), B=1000 slot-matched non-event samples, two-sided empirical p."""
    ev = events_for(df, inst, feat) if ev is None else ev
    R = df[f"R_{h}"].to_numpy(float).copy(); slot = df.slot.to_numpy(); date = df.date.to_numpy()
    idx_all = np.flatnonzero(ev & ~np.isnan(R))
    if inject: R[idx_all] += inject                                   # INJ±: event bars only (PREREG §9)
    hb = HB.get(h, 10**9); kept = thin(idx_all, date, hb) if h != "close" else idx_all
    if len(kept) == 0: return {"inst": inst, "feature": feat, "horizon": h, "n_raw": int(len(idx_all)), "n_eff": 0, "note": "no events with defined return"}
    nonev = ~ev & ~np.isnan(R); need = pd.Series(slot[kept]).value_counts().to_dict()
    pools = {s: np.flatnonzero(nonev & (slot == s)) for s in need}
    means = np.empty(B)
    for b in range(B):
        rng = np.random.default_rng([seed, b])          # seed sequence: distinct streams per (seed, draw); 'seed + b' overlapped across seeds
        picks = np.concatenate([rng.choice(pools[s], size=n, replace=False) for s, n in need.items()])
        means[b] = R[picks].mean()
    base = float(means.mean()); mean_ev = float(R[kept].mean()); diff = mean_ev - base
    p = float((1 + np.sum(np.abs(means - base) >= abs(diff))) / (B + 1))
    mm = PW["instruments"][inst]["mean_mid"]
    return {"inst": inst, "feature": feat, "horizon": h, "n_raw": int(len(idx_all)), "n_eff": int(len(kept)), "mean_event_pts": mean_ev, "baseline_mean_pts": base,
            "diff_pts": float(diff), "diff_bps": float(diff / mm * 1e4), "sd_event_pts": float(R[kept].std(ddof=1)) if len(kept) > 1 else float("nan"),
            "sd_nonevent_pts": float(R[nonev].std(ddof=1)), "sd_of_baseline_means_pts": float(means.std(ddof=1)), "p_two_sided": p,
            "raw_mean_event_pts": float(R[idx_all].mean()), "sign": int(np.sign(diff))}

def cell_verdict(a, b):
    """PREREG §6–§7 on the two instruments' results a (NIFTY_FUT) and b (BANKNIFTY_FUT)."""
    if "note" in a or "note" in b: return "NOT SCORED"
    same = a["sign"] == b["sign"] and a["sign"] != 0
    if not same: return "FAIL (sign flip)"
    if a["p_two_sided"] <= ALPHA and b["p_two_sided"] <= ALPHA and a["n_eff"] >= MIN_NEFF and b["n_eff"] >= MIN_NEFF: return "PRE-COST PASS / PENDING"
    return "FAIL"
