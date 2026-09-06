"""CP4 — recompute every usable session from scratch (same unmodified engine) into features_recheck/ and compare
byte-for-byte and row-for-row with the stored features; per-session triggered-event table for the SINGLE-EPISODE gate."""
import json, sys, time, hashlib, numpy as np, pandas as pd
from pathlib import Path
DE = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(DE / "scripts")); from features import compute
PW = json.loads((DE / "cp2_power.json").read_text()); EXCL = set(PW["excluded"]); inv = [r for r in json.loads((DE / "cp1_inventory.json").read_text()) if "key" in r and r["date"] not in EXCL]
RC = DE / "features_recheck"; RC.mkdir(exist_ok=True); t0 = time.time(); eq_bytes = eq_rows = 0; diffs = []
for r in inv:
    out = RC / f"{r['date']}_{r['inst']}.parquet"; compute(r["date"], r["inst"], r["key"], out)
    a, b = (DE / "features" / out.name).read_bytes(), out.read_bytes(); eq_bytes += (a == b)
    fa, fb = pd.read_parquet(DE / "features" / out.name), pd.read_parquet(out); same_rows = fa.equals(fb) or (fa.shape == fb.shape and all(np.allclose(fa[c].to_numpy(float), fb[c].to_numpy(float), equal_nan=True) for c in fa.columns)); eq_rows += same_rows
    if not (a == b and same_rows): diffs.append(out.name)
print(f"  recomputed {len(inv)} sessions from scratch in {time.time()-t0:.0f}s | byte-identical: {eq_bytes}/{len(inv)} | row-identical: {eq_rows}/{len(inv)} | differing: {diffs}")
# per-session triggered events per feature (thresholds frozen in cp2_power.json)
FE = ["bid_refills", "ask_refills", "bid_refill_ratio", "ask_refill_ratio", "bid_refills_w", "ask_refills_w"]; table = {}
for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
    thr = {f: {int(k): v for k, v in PW["instruments"][inst]["features"][f]["thresholds_by_slot"].items()} for f in FE}
    for p in sorted((DE / "features").glob(f"*_{inst}.parquet")):
        d = p.name[:10]
        if d in EXCL: continue
        f = pd.read_parquet(p); rec = {"rows_in": None, "bars": len(f)}
        for feat in FE:
            x = f[feat].to_numpy(float); T = f.slot.map(thr[feat]).to_numpy(float); rec[feat] = int(np.sum(~np.isnan(x) & (x > T)))
        table.setdefault(inst, {})[d] = rec
summ = {s["date"] + "_" + s["inst"]: s for s in json.loads((DE / "features/_summary.json").read_text())}
for inst in table:
    for d in table[inst]: table[inst][d]["rows_in"] = summ[f"{d}_{inst}"]["rows_in"]; table[inst][d]["refill_events_bid_ask"] = [summ[f"{d}_{inst}"]["refill_events"]["bid"], summ[f"{d}_{inst}"]["refill_events"]["ask"]]
(DE / "cp4_events_by_session.json").write_text(json.dumps({"recheck": {"sessions": len(inv), "byte_identical": eq_bytes, "row_identical": eq_rows, "differing": diffs}, "events": table}, indent=1))
for inst in table:
    print(f"  {inst}: per-session triggered events (rows_in | refills bid/ask | " + " | ".join(FE) + ")")
    for d, rec in table[inst].items(): print(f"    {d} {rec['rows_in']:>7} | {rec['refill_events_bid_ask'][0]:>5}/{rec['refill_events_bid_ask'][1]:<5} | " + " | ".join(f"{rec[f]:>4}" for f in FE))
    tot = {f: sum(rec[f] for rec in table[inst].values()) for f in FE}; ses = {f: sum(1 for rec in table[inst].values() if rec[f] > 0) for f in FE}
    print("    TOTAL " + " | ".join(f"{f}={tot[f]} over {ses[f]} sessions" for f in FE))
