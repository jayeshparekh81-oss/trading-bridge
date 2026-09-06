"""CP4 (run 3) — F1 / F2 events on DISCOVERY only (thresholds and sigma-quintile edges frozen in cp2_baseline.json / PREREG3),
written to features_discovery/; per-session spread; SINGLE-EPISODE gate; self-check = one session recomputed from scratch
and diffed byte-for-byte; the guard's access log audited (no confirmation date read before CP6)."""
import sys, json, time, numpy as np, pandas as pd
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); sys.path.insert(0, str(D3 / "scripts")); import first_passage as FP, qguard, scorer3 as S
q = json.loads((D3 / "QUARANTINE.json").read_text()); disc, conf = q["discovery"], q["confirmation"]; cp2 = json.loads((D3 / "cp2_baseline.json").read_text())
FD = D3 / "features_discovery"; FD.mkdir(exist_ok=True); FP_DIR = D3 / "fp_discovery"
def mark_events(df, inst):
    thr = cp2["instruments"][inst]["thresholds"]; edges = cp2["instruments"][inst]["sigma_quintile_edges"]
    bid = df.bid_refills.to_numpy(float) > df.slot.map({int(k): v for k, v in thr["bid"].items()}).to_numpy(float); ask = df.ask_refills.to_numpy(float) > df.slot.map({int(k): v for k, v in thr["ask"].items()}).to_numpy(float)
    usable = ~np.isnan(df.sigma_1m.to_numpy(float)) & ~np.isnan(df.censor_s.to_numpy(float)); df["usable"] = usable; df["sbucket"] = np.digitize(df.sigma_1m.to_numpy(float), edges)
    df["dir"] = np.where(bid & ~ask, 1, np.where(ask & ~bid, -1, 0)) * usable; df["F1"] = df["dir"] != 0; df["F2"] = df["F1"] & df.near_any.to_numpy(bool) & df.prev_levels_defined.to_numpy(bool)
    return df
if __name__ == "__main__":
    out = {}
    for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
        frames = []
        for d in disc: f = pd.read_parquet(FP_DIR / f"{d}_{inst}.parquet"); f["date"] = d; frames.append(mark_events(f, inst))
        df = pd.concat(frames, ignore_index=True); date = df.date.to_numpy(); be = df.bar_end_s.to_numpy(float); rec = {}
        for feat in ("F1", "F2"):
            idx = np.flatnonzero(df[feat].to_numpy(bool)); kept = S.thin(idx, date, be); df[f"{feat}_thin"] = False; df.loc[kept, f"{feat}_thin"] = True
            per = pd.Series(date[kept]).value_counts(); ses = int(len(per)); top = per.idxmax() if len(per) else None; share = float(per.max() / len(kept)) if len(kept) else 0
            rec[feat] = {"raw": int(len(idx)), "thinned": int(len(kept)), "sessions_with_events": ses, "per_session_min_med_max": [int(per.min()), float(per.median()), int(per.max())] if len(per) else [0, 0, 0], "top_session": top, "top_share": share, "rate_per_session": len(kept) / len(disc), "dir_split": {"+1 (bid burst)": int((df.loc[kept, "dir"] == 1).sum()), "-1 (ask burst)": int((df.loc[kept, "dir"] == -1).sum())}, "verdict": "SINGLE-EPISODE (excluded)" if ses < 3 else ("spread OK" + ("; CONCENTRATION FLAG" if share >= 0.30 else ""))}
            print(f"  {inst} {feat}: raw {len(idx)} thinned(>=300 s) {len(kept)} in {ses} sessions; per-session min/med/max {rec[feat]['per_session_min_med_max']}; top {top} ({share:.0%}); dir +1/-1 {rec[feat]['dir_split']}; -> {rec[feat]['verdict']}")
        ev = df[df.F1].copy(); ev.to_parquet(FD / f"events_{inst}.parquet", index=False); out[inst] = rec
        for d in disc: df[df.date == d].drop(columns=["date"]).to_parquet(FD / f"{d}_{inst}.parquet", index=False)
    # self-check 1: recompute one discovery session from scratch (stage CP4) and diff bytes against the CP2-written file
    d0, i0 = disc[3], "BANKNIFTY_FUT"; prev = None
    summ = json.loads((FP_DIR / "_summary.json").read_text()); prev_s = [s for s in summ if s["inst"] == i0 and s["date"] < d0]; prev = prev_s[-1]["this_session_levels"] if prev_s else None
    tmp = D3 / "fp_recheck"; tmp.mkdir(exist_ok=True); FP.compute_session(d0, i0, "CP4", prev, tmp / f"{d0}_{i0}.parquet")
    same = (tmp / f"{d0}_{i0}.parquet").read_bytes() == (FP_DIR / f"{d0}_{i0}.parquet").read_bytes(); print(f"  self-check recompute {d0} {i0} from scratch: {'BYTE-IDENTICAL' if same else 'DIFFERS'}")
    # self-check 2: access log audit
    log = qguard.access_log(); allowed = [r for r in log if r.get("allowed")]; conf_reads = [r for r in allowed if r["date"] in conf]; denied = [r for r in log if not r.get("allowed")]
    by_stage = pd.Series([r["stage"] for r in allowed]).value_counts().to_dict()
    print(f"  access log: allowed reads by stage {by_stage}; confirmation-date reads so far: {len(conf_reads)} (must be 0 before CP6); denied attempts (guard test): {len(denied)}")
    out["access_log_audit"] = {"allowed_by_stage": by_stage, "confirmation_reads_before_cp6": len(conf_reads), "denied": len(denied)}; out["recheck_byte_identical"] = bool(same)
    (D3 / "cp4_events.json").write_text(json.dumps(out, indent=1))
