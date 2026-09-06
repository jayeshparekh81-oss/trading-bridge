"""CP4 (run 2) — recompute sessions from scratch into features_recheck/ and diff byte/row against stored; per-session
triggered-event table (thresholds frozen in cp2_power2.json) for the SINGLE-EPISODE gate."""
import json, sys, time, numpy as np, pandas as pd
from pathlib import Path
D2 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D2)); sys.path.insert(0, str(D2 / "scripts")); from deep_book import compute_session; import cp2_power2 as C
PW = json.loads((D2 / "cp2_power2.json").read_text()); cp0 = {(r["date"], r["inst"]): r for r in json.loads((D2 / "cp0_integrity.json").read_text()) if "key" in r}
PICK = [("2026-07-14", "NIFTY_FUT"), ("2026-07-29", "BANKNIFTY_FUT"), ("2026-08-26", "BANKNIFTY_FUT"), ("2026-09-04", "NIFTY_FUT")]
RC = D2 / "features_recheck"; RC.mkdir(exist_ok=True); res = []
for d, inst in PICK:
    t0 = time.time(); out = RC / f"{d}_{inst}.parquet"; compute_session(d, inst, cp0[(d, inst)]["key"], out)
    a, b = (D2 / "features" / out.name).read_bytes(), out.read_bytes(); fa, fb = pd.read_parquet(D2 / "features" / out.name), pd.read_parquet(out)
    rows_same = fa.shape == fb.shape and all(np.allclose(fa[c].to_numpy(float), fb[c].to_numpy(float), equal_nan=True) for c in fa.columns)
    res.append({"session": out.name, "byte_identical": a == b, "row_identical": bool(rows_same)}); print(f"  recheck {out.name}: bytes {'IDENTICAL' if a == b else 'DIFFER'} rows {'IDENTICAL' if rows_same else 'DIFFER'} ({time.time()-t0:.0f}s)")
FE = list(PW["instruments"]["NIFTY_FUT"]["features"].keys()); table = {}; summ = {(s["date"], s["inst"]): s for s in json.loads((D2 / "features/_summary.json").read_text())}
for inst in ("NIFTY_FUT", "BANKNIFTY_FUT"):
    df = C.load(inst); date = df.date.to_numpy(); per = {}
    for f in FE:
        thr = {int(k): v for k, v in PW["instruments"][inst]["features"][f]["thresholds_by_slot"].items()}
        ev = (C.events_signed(df, f, thr)[0] if f in C.SIGNED else C.events_count(df, f, thr)[0])
        per[f] = pd.Series(date[ev]).value_counts().to_dict()
    dates = sorted(df.date.unique()); table[inst] = {d: {"rows_in": summ[(d, inst)]["rows_in"], **{f: int(per[f].get(d, 0)) for f in FE}} for d in dates}
    print(f"\n  {inst}: per-session triggered events (" + ", ".join(FE) + ")")
    for d in dates: print(f"    {d} rows={table[inst][d]['rows_in']:>7} | " + " ".join(f"{table[inst][d][f]:>4}" for f in FE))
    for f in FE:
        tot = sum(per[f].values()); ses = sum(1 for v in per[f].values() if v > 0); top = max(per[f], key=per[f].get); share = per[f][top] / tot
        flag = "SINGLE-EPISODE" if ses < 3 else ("CONCENTRATION FLAG" if share >= 0.30 else "ok")
        print(f"    {f:<22} total={tot:>5} sessions={ses:>2} top={top} ({share:.0%}) -> {flag}")
(D2 / "cp4_events_by_session2.json").write_text(json.dumps({"recheck": res, "events": table}, indent=1))
