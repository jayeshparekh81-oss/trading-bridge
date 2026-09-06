"""CP6 (run 3) — score DISCOVERY exactly per PREREG3, freeze the passing cells, then unlock CONFIRMATION (stage CP6),
read it ONCE, score only the frozen cells; head-to-head vs run 1; determinism via --tag."""
import sys, json, time, numpy as np, pandas as pd
from pathlib import Path
D3 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D3)); sys.path.insert(0, str(D3 / "scripts")); import first_passage as FP, scorer3 as S, qguard
from cp4_events import mark_events
tag = sys.argv[1] if len(sys.argv) > 1 else "run1"; DO_CONF = "--confirm" in sys.argv
q = json.loads((D3 / "QUARANTINE.json").read_text()); disc, conf = q["discovery"], q["confirmation"]; cp2 = json.loads((D3 / "cp2_baseline.json").read_text()); FD = D3 / "features_discovery"; I = ("NIFTY_FUT", "BANKNIFTY_FUT")
def load_set(dates, folder, inst):
    return pd.concat([pd.read_parquet(folder / f"{d}_{inst}.parquet").assign(date=d) for d in dates], ignore_index=True)
def score_set(df, inst, feats, pairs, seed):
    out = {}
    for feat in feats:
        idx = np.flatnonzero(df[f"{feat}_thin"].to_numpy(bool)); dir_all = np.where(df[f"{feat}_thin"].to_numpy(bool), df["dir"].to_numpy(), 0)
        for a, b in pairs: r = S.score_cell(df, idx, dir_all, a, b, seed=seed); r["feature"] = feat; r["inst"] = inst; out[(feat, a, b)] = r
    return out
res = {"alpha": S.ALPHA, "n_hyp_all_runs": S.N_HYP_ALL_RUNS, "discovery": {}, "frozen": [], "confirmation": {}, "confirmation_read": False}
t0 = time.time(); disc_df = {i: load_set(disc, FD, i) for i in I}; D = {i: score_set(disc_df[i], i, ("F1", "F2"), S.PAIRS, S.SEED) for i in I}
print(f"  DISCOVERY scored ({time.time()-t0:.0f}s); alpha = {S.ALPHA:.6f} on both instruments; same sign; n_resolved >= {S.MIN_RESOLVED}")
print("  feature pair  | NIFTY n/res  win%  base%  theory  lift_pp  p       E[R]   | BANKNIFTY n/res  win%  base%  lift_pp  p       E[R]   | same sign | verdict")
cells = []
for key in D["NIFTY_FUT"]:
    a, b = D["NIFTY_FUT"][key], D["BANKNIFTY_FUT"][key]; v = S.cell_verdict(a, b); cells.append({"feature": key[0], "stop": key[1], "target": key[2], "NIFTY_FUT": a, "BANKNIFTY_FUT": b, "same_sign": a["sign"] == b["sign"] and a["sign"] != 0, "verdict": v})
    print(f"  {key[0]} {key[1]}:{key[2]} | {a['n_events']:>4}/{a['n_resolved']:<4} {a['win_rate']*100:5.1f} {a['baseline_win_rate']*100:5.1f} {a['theory']*100:5.1f} {a['lift_pp']:+6.1f} {a['p_two_sided']:.4f} {a['expectancy_R']:+.3f} | {b['n_events']:>4}/{b['n_resolved']:<4} {b['win_rate']*100:5.1f} {b['baseline_win_rate']*100:5.1f} {b['lift_pp']:+6.1f} {b['p_two_sided']:.4f} {b['expectancy_R']:+.3f} | {'yes' if a['sign']==b['sign'] and a['sign']!=0 else 'NO '} | {v}")
res["discovery"] = cells; frozen = [c for c in cells if c["verdict"].startswith("PASS")]; res["frozen"] = [(c["feature"], c["stop"], c["target"]) for c in frozen]
print(f"  FROZEN cells passing discovery: {res['frozen'] if frozen else 'NONE'}")
if DO_CONF:
    res["confirmation_read"] = True; summ = json.loads((D3 / "fp_discovery" / "_summary.json").read_text()); FC = D3 / "fp_confirmation"; FC.mkdir(exist_ok=True); csum = []
    for inst in I:
        prev = [s for s in summ if s["inst"] == inst][-1]["this_session_levels"]           # previous clean session of the first confirmation date = the last discovery date
        for d in conf:
            p = FC / f"{d}_{inst}.parquet"
            if not p.exists(): _, s = FP.compute_session(d, inst, "CP6", prev, p); csum.append(s); prev = s["this_session_levels"]; print(f"  CP6 read {d} {inst} rows={s['rows_in']} refills b/a={s['refill_events']['bid']}/{s['refill_events']['ask']}", flush=True)
            else: prev = json.loads((FC / "_summary.json").read_text()) and [x for x in json.loads((FC / "_summary.json").read_text()) if x["date"] == d and x["inst"] == inst][0]["this_session_levels"]
    if csum: (FC / "_summary.json").write_text(json.dumps(csum, indent=1))
    conf_df = {}
    for inst in I:
        df = load_set(conf, FC, inst); df = mark_events(df, inst); date = df.date.to_numpy(); be = df.bar_end_s.to_numpy(float)
        for feat in ("F1", "F2"):
            idx = np.flatnonzero(df[feat].to_numpy(bool)); kept = S.thin(idx, date, be); df[f"{feat}_thin"] = False; df.loc[kept, f"{feat}_thin"] = True
        conf_df[inst] = df; res["confirmation"][inst] = {"F1_thinned": int(df.F1_thin.sum()), "F2_thinned": int(df.F2_thin.sum()), "sessions": len(conf)}
        print(f"  CONFIRMATION {inst}: F1 thinned events {int(df.F1_thin.sum())}, F2 {int(df.F2_thin.sum())} over {len(conf)} sessions")
    if frozen:
        C = {i: score_set(conf_df[i], i, sorted({c['feature'] for c in frozen}), sorted({(c['stop'], c['target']) for c in frozen}), S.SEED + 1) for i in I}; crows = []
        for c in frozen:
            key = (c["feature"], c["stop"], c["target"]); a, b = C["NIFTY_FUT"][key], C["BANKNIFTY_FUT"][key]; va, vb = S.confirm_verdict(c["NIFTY_FUT"], a), S.confirm_verdict(c["BANKNIFTY_FUT"], b)
            crows.append({"feature": key[0], "stop": key[1], "target": key[2], "NIFTY_FUT": a, "BANKNIFTY_FUT": b, "verdict_NIFTY": va, "verdict_BANKNIFTY": vb, "verdict": "CONFIRMED (PRE-COST / PENDING)" if va.startswith("CONFIRMED") and vb.startswith("CONFIRMED") else "FAIL confirmation"})
            print(f"  CONFIRM {key}: NIFTY lift {a['lift_pp']:+.1f} pp (disc {c['NIFTY_FUT']['lift_pp']:+.1f}) p={a['p_two_sided']:.4f} -> {va} | BANKNIFTY lift {b['lift_pp']:+.1f} pp (disc {c['BANKNIFTY_FUT']['lift_pp']:+.1f}) p={b['p_two_sided']:.4f} -> {vb}")
        res["confirmation"]["cells"] = crows
    else: print("  no frozen cell -> confirmation NOT scored (read once for event counts / actual power only)")
(D3 / f"cp6_result_{tag}.json").write_text(json.dumps(res, indent=1, default=float)); print(f"  written cp6_result_{tag}.json")
